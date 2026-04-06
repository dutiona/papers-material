"""Router: dispatches retrieval queries to the appropriate store based on classification.

Typed routing condition:
- contradiction_resolution → KB (supersession-aware retrieval)
- temporal_reasoning → ME (bi-temporal retrieval)

Flat baseline condition:
- All queries → flat store (FTS only, no type semantics)
"""

from __future__ import annotations

import re

from baseline.store import FlatStore
from classifier.router import RouterMode, classify
from dataset.types import ProbingQuestion, QueryRoute
from routing.kb_store import KBStore
from routing.me_store import MEStore


def _to_search_keywords(text: str) -> str:
    """Convert a natural language question into FTS5-safe search keywords.

    Strips punctuation, stopwords, and short words to produce a keyword query
    that works across FTS5 (KB, flat) and ME CLI search.
    """
    _stopwords = frozenset(
        {
            "a",
            "an",
            "the",
            "is",
            "was",
            "are",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "can",
            "shall",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "between",
            "out",
            "off",
            "over",
            "under",
            "again",
            "further",
            "then",
            "once",
            "here",
            "there",
            "when",
            "where",
            "why",
            "how",
            "all",
            "each",
            "every",
            "both",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "no",
            "nor",
            "not",
            "only",
            "own",
            "same",
            "so",
            "than",
            "too",
            "very",
            "and",
            "but",
            "or",
            "if",
            "this",
            "that",
            "these",
            "those",
            "am",
            "i",
            "me",
            "my",
            "we",
            "our",
            "you",
            "your",
            "he",
            "him",
            "his",
            "she",
            "her",
            "it",
            "its",
            "they",
            "them",
            "their",
            "what",
            "which",
            "who",
            "whom",
            "ever",
        }
    )
    words = re.findall(r"\b\w+\b", text.lower())
    keywords = [w for w in words if w not in _stopwords and len(w) >= 3]
    # FTS5 default is AND between terms. Use OR for recall.
    return " OR ".join(keywords)


def retrieve_typed(
    question: ProbingQuestion,
    *,
    kb: KBStore,
    me: MEStore,
    router_mode: RouterMode = RouterMode.ORACLE,
    top_k: int = 10,
) -> tuple[str, QueryRoute]:
    """Retrieve context using typed routing (the experimental condition)."""
    route = classify(question, router_mode)
    query = _to_search_keywords(question.question)

    if route == QueryRoute.KNOWLEDGE:
        context = kb.retrieve_with_supersession(query, top_k=top_k)
    elif route == QueryRoute.MEMORY:
        context = me.retrieve_temporal(query, top_k=top_k)
    else:
        kb_ctx = kb.retrieve_with_supersession(query, top_k=top_k // 2)
        me_ctx = me.retrieve_temporal(query, top_k=top_k // 2)
        context = f"{kb_ctx}\n\n{me_ctx}"

    return context, route


def retrieve_flat(
    question: ProbingQuestion,
    *,
    flat: FlatStore,
    top_k: int = 10,
) -> str:
    """Retrieve context using the flat baseline (control condition)."""
    query = _to_search_keywords(question.question)
    results = flat.search(query, top_k=top_k)
    if not results:
        return "(no relevant context found)"

    parts = ["=== Retrieved conversation excerpts (flat store) ==="]
    for r in results:
        parts.append(r.content)
    return "\n\n".join(parts)
