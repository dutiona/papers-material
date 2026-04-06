"""Router: dispatches retrieval queries to the appropriate store based on classification.

Typed routing condition:
- contradiction_resolution → KB (supersession-aware retrieval)
- temporal_reasoning → ME (bi-temporal retrieval)

Flat baseline condition:
- All queries → flat store (FTS only, no type semantics)
"""

from __future__ import annotations

from baseline.store import FlatStore
from classifier.router import RouterMode, classify
from dataset.types import ProbingQuestion, QueryRoute
from routing.kb_store import KBStore
from routing.me_store import MEStore


def retrieve_typed(
    question: ProbingQuestion,
    *,
    kb: KBStore,
    me: MEStore,
    router_mode: RouterMode = RouterMode.ORACLE,
    top_k: int = 10,
) -> tuple[str, QueryRoute]:
    """Retrieve context using typed routing (the experimental condition).

    Routes to KB or ME based on classification, then retrieves context
    using the store's type-aware retrieval.

    Returns (context_string, route_taken).
    """
    route = classify(question, router_mode)

    if route == QueryRoute.KNOWLEDGE:
        context = kb.retrieve_with_supersession(question.question, top_k=top_k)
    elif route == QueryRoute.MEMORY:
        context = me.retrieve_temporal(question.question, top_k=top_k)
    else:
        # Mixed: query both, concatenate.
        kb_ctx = kb.retrieve_with_supersession(question.question, top_k=top_k // 2)
        me_ctx = me.retrieve_temporal(question.question, top_k=top_k // 2)
        context = f"{kb_ctx}\n\n{me_ctx}"

    return context, route


def retrieve_flat(
    question: ProbingQuestion,
    *,
    flat: FlatStore,
    top_k: int = 10,
) -> str:
    """Retrieve context using the flat baseline (control condition).

    All queries go to the same undifferentiated store. No supersession,
    no temporal filtering.
    """
    results = flat.search(question.question, top_k=top_k)
    if not results:
        return "(no relevant context found)"

    parts = ["=== Retrieved conversation excerpts (flat store) ==="]
    for r in results:
        parts.append(r.content)
    return "\n\n".join(parts)
