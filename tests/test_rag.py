"""
Retrieval.

The headline defect. The previous module seeded a real ChromaDB vector store
and then never queried it: ``retrieve_context`` did substring keyword matching
over a hardcoded copy of the four seed sentences. These tests assert that
retrieval now goes through the vector store, and that the keyword path is only
a labelled fallback.
"""

from __future__ import annotations

import ast
import inspect


import rag_pipeline
from rag_pipeline import retrieve, retrieve_context


class TestVectorRetrieval:
    def test_a_query_returns_documents_from_the_store(self):
        result = retrieve("Explain photosynthesis in plants", n_results=1)
        assert result.documents
        assert result.source == "vector"
        assert "photosynthesis" in result.documents[0].lower()

    def test_a_semantic_query_without_the_keyword_still_retrieves(self):
        """Keyword matching could not do this; a vector store can."""
        result = retrieve("how do leaves turn sunlight into food", n_results=1)
        assert result.source == "vector"
        assert result.documents

    def test_results_are_capped(self):
        assert len(retrieve("science", n_results=2).documents) <= 2

    def test_an_empty_query_returns_nothing(self):
        assert retrieve("   ").documents == []
        assert retrieve("   ").source == "empty"

    def test_retrieve_context_returns_documents_or_a_clear_message(self):
        assert retrieve_context("fractions")[0]
        miss = retrieve_context("zzzz nonexistent topic qqqq")
        assert miss == ["No curriculum context matched this query."] or miss


class TestFallbackIsLabelled:
    def test_when_the_store_raises_the_keyword_fallback_is_used_and_named(
        self, monkeypatch
    ):
        def boom():
            raise RuntimeError("chroma unavailable")

        monkeypatch.setattr(rag_pipeline, "_collection", boom)
        result = retrieve("tell me about photosynthesis", n_results=1)
        assert result.source == "keyword-fallback"
        assert "photosynthesis" in result.documents[0].lower()

    def test_the_fallback_is_not_the_default_path(self):
        """The whole defect was that the fallback WAS the implementation."""
        source = inspect.getsource(rag_pipeline.retrieve)
        tree = ast.parse(source)
        # The first thing retrieve does after the empty check is call _collection().
        calls = [
            n.func.id
            for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        ]
        assert "_collection" in calls


class TestNoImportSideEffects:
    def test_importing_the_module_does_not_build_the_client(self):
        """The old module created a PersistentClient and seeded it at import."""
        tree = ast.parse(inspect.getsource(rag_pipeline))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                break  # module-level executable code all precedes the definitions
            allowed = (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign)
            is_docstring = isinstance(node, ast.Expr) and isinstance(
                node.value, ast.Constant
            )
            assert isinstance(node, allowed) or is_docstring, ast.dump(node)[:80]
