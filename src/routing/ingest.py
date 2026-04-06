"""Ingestion pipeline: BEAM conversations → KB/ME/flat stores.

Option C design: ingest ALL turns into ALL stores. The difference is how
each store handles them:
- KB: turns as chunks + factual claims as conclusions with supersession
- ME: turns as facts with bi-temporal metadata via CLI
- Flat: turns as plain text chunks, no supersession, no temporal filtering

Contradiction detection for supersession uses a lightweight heuristic:
entity overlap + negation pattern matching between new user statements
and existing conclusions.
"""

from __future__ import annotations

import logging
import re

from baseline.store import FlatStore
from dataset.types import Conversation
from routing.kb_store import KBStore
from routing.me_store import MEStore

logger = logging.getLogger(__name__)

# Patterns that indicate a factual claim worth tracking as a conclusion.
_CLAIM_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"I (?:have|had|am|was|do|did|don't|never|always|usually|started|finished|completed|implemented|built|created|wrote|made|used|tried)",
        r"I (?:actually|recently|already|finally|just)\b",
        r"(?:my|our) (?:project|app|website|plan|budget|deadline|goal|schedule)",
        r"I (?:want|need|prefer|decided|chose|switched|moved|changed)",
        r"the (?:deadline|budget|timeline|schedule|plan) (?:is|was|will be)",
    ]
]

# Pure negation indicators (denying something).
_NEGATION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bnever\b",
        r"\bnot\b",
        r"\bno\b",
        r"\bdon'?t\b",
        r"\bdidn'?t\b",
        r"\bhaven'?t\b",
        r"\bwon'?t\b",
        r"\bcan'?t\b",
        r"\bstopped\b",
        r"\bquit\b",
    ]
]

# Correction indicators (revising a previous statement).
_CORRECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bactually\b",
        r"\binstead\b",
        r"\bchanged\b",
        r"\bturns out\b",
        r"\bin fact\b",
        r"\bended up\b",
    ]
]


def _is_factual_claim(text: str) -> bool:
    """Heuristic: does this text contain a user's factual statement?"""
    return any(p.search(text) for p in _CLAIM_PATTERNS)


def _extract_claim(turn_content: str) -> str:
    """Extract a simplified claim from a conversation turn.

    Takes the first sentence that matches a claim pattern, truncated to
    reasonable length for a conclusion.
    """
    sentences = re.split(r"[.!?]+", turn_content)
    for sentence in sentences:
        sentence = sentence.strip()
        if sentence and _is_factual_claim(sentence):
            return sentence[:300]
    # Fallback: first sentence.
    first = sentences[0].strip() if sentences else turn_content
    return first[:300]


_STOPWORDS = frozenset(
    {
        "have",
        "that",
        "this",
        "with",
        "from",
        "been",
        "will",
        "about",
        "just",
        "some",
        "more",
        "also",
        "very",
        "much",
        "would",
        "could",
        "should",
        "their",
        "there",
        "they",
        "what",
        "when",
        "which",
        "before",
        "after",
        "into",
        "does",
        "done",
        "make",
        "made",
    }
)


def _word_prefixes(words: set[str], min_len: int = 4) -> set[str]:
    """Generate 4-char prefixes for poor-man's stemming (route/routes/routing → rout)."""
    return {w[:min_len] for w in words if len(w) >= min_len}


def _has_negation_overlap(new_claim: str, existing_claim: str) -> bool:
    """Heuristic contradiction detection: do two claims share entities but
    differ in negation?

    Uses prefix matching for stemming (route ≈ routes) and requires at least
    1 meaningful shared entity with negation asymmetry.
    """
    new_words = set(re.findall(r"\b\w{3,}\b", new_claim.lower()))
    existing_words = set(re.findall(r"\b\w{3,}\b", existing_claim.lower()))

    # Exact overlap + prefix overlap (poor-man's stemming).
    exact_overlap = new_words & existing_words
    prefix_overlap = _word_prefixes(new_words) & _word_prefixes(existing_words)

    # Filter out stopwords.
    meaningful_exact = {w for w in exact_overlap if w not in _STOPWORDS and len(w) > 3}
    meaningful_prefix = {p for p in prefix_overlap if not any(s.startswith(p) for s in _STOPWORDS)}

    # Need at least 1 meaningful entity in common.
    if not meaningful_exact and len(meaningful_prefix) < 1:
        return False

    # Detect contradiction via signal asymmetry:
    # Case 1: one has negation, the other doesn't (classic negation flip).
    # Case 2: existing has negation, new has correction signal ("actually", "instead").
    # Case 3: new has negation, existing doesn't (new denial of old positive).
    new_has_neg = any(p.search(new_claim) for p in _NEGATION_PATTERNS)
    old_has_neg = any(p.search(existing_claim) for p in _NEGATION_PATTERNS)
    new_has_correction = any(p.search(new_claim) for p in _CORRECTION_PATTERNS)

    # Pure negation asymmetry.
    if new_has_neg != old_has_neg:
        return True
    # Correction overriding a negation (e.g., "I never X" → "I actually X'd").
    if old_has_neg and new_has_correction:
        return True

    return False


def ingest_conversation_kb(
    conversation: Conversation,
    store: KBStore,
) -> dict[str, int]:
    """Ingest a BEAM conversation into the KB store.

    1. All turns inserted as searchable chunks (FTS).
    2. User turns with factual claims recorded as conclusions.
    3. Contradictions detected and recorded as supersessions.

    Returns stats: {chunks, claims, supersessions}.
    """
    stats = {"chunks": 0, "claims": 0, "supersessions": 0}

    # Step 1: Bulk insert all turns as chunks.
    all_turns = conversation.all_turns
    count = store.ingest_turns_batch(all_turns, conversation.conversation_id)
    stats["chunks"] = count

    # Step 2: Process user turns for factual claims.
    for turn in all_turns:
        if turn.role != "user":
            continue
        if not _is_factual_claim(turn.content):
            continue

        claim_text = _extract_claim(turn.content)

        # Check for contradictions with existing active conclusions.
        existing = store.get_active_conclusions()
        superseded = False
        for existing_claim in existing:
            if _has_negation_overlap(claim_text, str(existing_claim["claim"])):
                store.supersede_claim(
                    int(existing_claim["id"]),
                    claim_text,
                    context=f"Contradiction detected in turn {turn.turn_id}",
                )
                stats["supersessions"] += 1
                superseded = True
                break  # One supersession per new claim.

        if not superseded:
            store.record_claim(
                claim_text,
                context=f"From turn {turn.turn_id}",
            )
            stats["claims"] += 1

    return stats


def ingest_conversation_flat(
    conversation: Conversation,
    store: FlatStore,
) -> int:
    """Ingest a BEAM conversation into the flat baseline store.

    All turns inserted as plain text. No supersession, no temporal filtering.
    Returns the number of rows inserted.
    """
    rows = [
        (
            turn.content,
            conversation.conversation_id,
            turn.turn_id,
            turn.role,
            turn.time_anchor,
            "{}",
        )
        for turn in conversation.all_turns
    ]
    return store.ingest_batch(rows)


def ingest_conversation_me(
    conversation: Conversation,
    store: MEStore,
) -> int:
    """Ingest a BEAM conversation into the memory-engine store.

    All turns inserted as facts with bi-temporal metadata.
    The ME store handles embedding and temporal indexing via the CLI.
    Returns the number of facts ingested.
    """
    return store.ingest_turns(conversation.all_turns, conversation.conversation_id)
