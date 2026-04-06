"""Experiment runner: end-to-end BEAM typed-routing pilot.

Orchestrates: load data → ingest into all stores → for each question,
run both conditions (typed routing + flat baseline) → score → report.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from baseline.store import FlatStore
from classifier.router import RouterMode
from config import Config
from dataset.loader import load_beam
from dataset.types import Conversation, ProbingQuestion, QuestionCategory
from evaluation.llm import generate_answer, score_answer
from evaluation.types import ExperimentReport, TrialResult
from routing.ingest import ingest_conversation_flat, ingest_conversation_kb, ingest_conversation_me
from routing.kb_store import KBStore
from routing.me_store import MEStore
from routing.router import retrieve_flat, retrieve_typed

logger = logging.getLogger(__name__)


def run_experiment(
    *,
    cfg: Config | None = None,
    split: str = "100K",
    max_conversations: int | None = None,
    router_mode: RouterMode = RouterMode.ORACLE,
    top_k: int = 10,
) -> ExperimentReport:
    """Run the full BEAM typed-routing pilot experiment.

    Args:
        cfg: Experiment configuration.
        split: BEAM dataset split ("100K", "500K", "1M").
        max_conversations: Limit conversations (for smoke tests).
        router_mode: ORACLE (ground truth) or HEURISTIC.
        top_k: Number of chunks to retrieve per query.

    Returns:
        ExperimentReport with all trial results.
    """
    c = cfg or Config()
    c.data_dir.mkdir(parents=True, exist_ok=True)
    c.results_dir.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Load dataset ──────────────────────────────────────
    logger.info("Loading BEAM dataset (split=%s)...", split)
    conversations = load_beam(split)
    if max_conversations:
        conversations = conversations[:max_conversations]
    logger.info("Using %d conversations", len(conversations))

    # ── Step 2: Ingest into all stores ────────────────────────────
    logger.info("Ingesting into stores...")
    kb = KBStore(c.kb_db_path, cfg=c)
    me = MEStore(c.me_db_path, cfg=c)
    flat = FlatStore(c.flat_db_path)

    for i, conv in enumerate(conversations):
        t0 = time.time()
        kb_stats = ingest_conversation_kb(conv, kb)
        me_count = ingest_conversation_me(conv, me)
        flat_count = ingest_conversation_flat(conv, flat)
        elapsed = time.time() - t0
        logger.info(
            "  Conv %s (%d/%d): KB=%s, ME=%d, flat=%d [%.1fs]",
            conv.conversation_id,
            i + 1,
            len(conversations),
            kb_stats,
            me_count,
            flat_count,
            elapsed,
        )

    logger.info(
        "Ingestion complete: KB=%d chunks/%d conclusions, flat=%d chunks",
        kb.chunk_count(),
        kb.conclusion_count(),
        flat.count(),
    )

    # ── Step 3: Run trials ────────────────────────────────────────
    trials: list[TrialResult] = []
    all_questions = [q for conv in conversations for q in conv.experiment_questions]
    logger.info(
        "Running %d trials (×2 conditions = %d LLM calls)...",
        len(all_questions),
        len(all_questions) * 4,
    )

    for i, question in enumerate(all_questions):
        logger.info(
            "  Q %d/%d [%s]: %s",
            i + 1,
            len(all_questions),
            question.category.value,
            question.question[:60],
        )

        # ── Typed routing condition ───────────────────────────────
        typed_context, route = retrieve_typed(
            question,
            kb=kb,
            me=me,
            router_mode=router_mode,
            top_k=top_k,
        )
        typed_answer = generate_answer(question.question, typed_context, cfg=c)
        typed_score, typed_justification = score_answer(
            question.question,
            question.ideal_answer,
            typed_answer,
            question.category,
            cfg=c,
        )

        trials.append(
            TrialResult(
                question_text=question.question,
                ideal_answer=question.ideal_answer,
                generated_answer=typed_answer,
                retrieved_context=typed_context[:500],  # Truncate for storage.
                category=question.category,
                route=route,
                conversation_id=question.conversation_id,
                condition="typed",
                score=typed_score,
                justification=typed_justification,
            )
        )

        # ── Flat baseline condition ───────────────────────────────
        flat_context = retrieve_flat(question, flat=flat, top_k=top_k)
        flat_answer = generate_answer(question.question, flat_context, cfg=c)
        flat_score, flat_justification = score_answer(
            question.question,
            question.ideal_answer,
            flat_answer,
            question.category,
            cfg=c,
        )

        trials.append(
            TrialResult(
                question_text=question.question,
                ideal_answer=question.ideal_answer,
                generated_answer=flat_answer,
                retrieved_context=flat_context[:500],
                category=question.category,
                route=route,
                conversation_id=question.conversation_id,
                condition="flat",
                score=flat_score,
                justification=flat_justification,
            )
        )

        logger.info(
            "    typed=%.2f flat=%.2f (route=%s)",
            typed_score,
            flat_score,
            route.value,
        )

    # ── Step 4: Report ────────────────────────────────────────────
    report = ExperimentReport(trials=trials)
    _save_report(report, c.results_dir)

    logger.info("=== RESULTS ===")
    for cat, scores in report.mean_by_category_and_condition().items():
        logger.info(
            "  %s: typed=%.3f flat=%.3f (delta=%+.3f)",
            cat,
            scores["typed"],
            scores["flat"],
            scores["typed"] - scores["flat"],
        )

    kb.close()
    flat.close()

    return report


def _save_report(report: ExperimentReport, results_dir: Path) -> None:
    """Save experiment results to JSON."""
    results_dir.mkdir(parents=True, exist_ok=True)

    # Summary.
    summary = {
        "mean_by_category": report.mean_by_category(),
        "mean_by_condition": report.mean_by_condition(),
        "mean_by_category_and_condition": report.mean_by_category_and_condition(),
        "total_trials": len(report.trials),
    }
    summary_path = results_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    logger.info("Summary saved to %s", summary_path)

    # Full trial data.
    trials_data = [
        {
            "question": t.question_text,
            "ideal_answer": t.ideal_answer,
            "generated_answer": t.generated_answer,
            "category": t.category.value,
            "route": t.route.value,
            "conversation_id": t.conversation_id,
            "condition": t.condition,
            "score": t.score,
            "justification": t.justification,
        }
        for t in report.trials
    ]
    trials_path = results_dir / "trials.json"
    trials_path.write_text(json.dumps(trials_data, indent=2))
    logger.info("Full trials saved to %s", trials_path)


# ── CLI entry point ───────────────────────────────────────────────


def main() -> None:
    """Run from command line: PYTHONPATH=src uv run python -m experiment"""
    import argparse

    parser = argparse.ArgumentParser(description="BEAM typed-routing pilot experiment")
    parser.add_argument("--split", default="100K", choices=["100K", "500K", "1M"])
    parser.add_argument(
        "--max-conversations", type=int, default=None, help="Limit conversations (for smoke tests)"
    )
    parser.add_argument("--router", default="oracle", choices=["oracle", "heuristic"])
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    cfg = Config()
    report = run_experiment(
        cfg=cfg,
        split=args.split,
        max_conversations=args.max_conversations,
        router_mode=RouterMode(args.router),
        top_k=args.top_k,
    )

    # Print summary table.
    print("\n" + "=" * 60)
    print("BEAM Typed-Routing Pilot — Results")
    print("=" * 60)
    results = report.mean_by_category_and_condition()
    for cat, scores in results.items():
        delta = scores["typed"] - scores["flat"]
        print(
            f"  {cat:30s}  typed={scores['typed']:.3f}  flat={scores['flat']:.3f}  Δ={delta:+.3f}"
        )
    overall = report.mean_by_condition()
    delta_overall = overall["typed"] - overall["flat"]
    print(
        f"  {'OVERALL':30s}  typed={overall['typed']:.3f}  flat={overall['flat']:.3f}  Δ={delta_overall:+.3f}"
    )
    print("=" * 60)


if __name__ == "__main__":
    main()
