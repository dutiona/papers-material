"""Tests for the flat baseline store."""

from __future__ import annotations

from baseline.store import FlatStore, SearchResult


class TestFlatStore:
    def test_ingest_and_count(self) -> None:
        with FlatStore() as store:
            store.ingest("The capital of France is Paris", conversation_id="1", turn_id=1)
            store.ingest("The capital of Germany is Berlin", conversation_id="1", turn_id=2)
            assert store.count() == 2

    def test_search_returns_relevant(self) -> None:
        with FlatStore() as store:
            store.ingest("The capital of France is Paris")
            store.ingest("Python is a programming language")
            store.ingest("France has a population of 67 million")

            results = store.search("France capital")
            assert len(results) > 0
            assert isinstance(results[0], SearchResult)
            # The Paris fact should rank higher than the population fact
            assert "Paris" in results[0].content

    def test_search_empty_store(self) -> None:
        with FlatStore() as store:
            results = store.search("anything")
            assert results == []

    def test_search_top_k(self) -> None:
        with FlatStore() as store:
            for i in range(20):
                store.ingest(f"Fact number {i} about testing search")
            results = store.search("testing search", top_k=5)
            assert len(results) <= 5

    def test_ingest_batch(self) -> None:
        with FlatStore() as store:
            rows = [
                ("Fact one", "conv1", 1, "user", "March-15", "{}"),
                ("Fact two", "conv1", 2, "assistant", "March-16", "{}"),
                ("Fact three", "conv1", 3, "user", "March-17", "{}"),
            ]
            count = store.ingest_batch(rows)
            assert count == 3
            assert store.count() == 3

    def test_no_temporal_filtering(self) -> None:
        """The flat store stores time_anchor but does NOT filter by it.
        All facts are always returned regardless of temporal context."""
        with FlatStore() as store:
            store.ingest("Meeting on March 15", time_anchor="March-15")
            store.ingest("Meeting on March 20", time_anchor="March-20")
            store.ingest("Meeting on April 1", time_anchor="April-01")

            results = store.search("Meeting")
            assert len(results) == 3  # All returned, no temporal filtering
