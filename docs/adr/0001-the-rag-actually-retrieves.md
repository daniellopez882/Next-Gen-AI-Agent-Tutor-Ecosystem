# ADR 0001 — The RAG actually queries the vector store

**Status:** accepted

## Context

`rag_pipeline.py` built a real ChromaDB persistent client at import, seeded it
with four documents and their embeddings — and then `retrieve_context`
**ignored the store entirely**:

```python
# Since ONNX inference is sometimes unstable on certain Windows environments,
# we use a highly reliable keyword-based RAG fallback for the local prototype.
if "photosynthesis" in query_lower or "plant" in query_lower:
    matched.append(fallback_docs[0])
```

So the "vector database" was seeded and never read; retrieval was substring
matching over a hardcoded copy of the same four sentences (`"math" in query`
also matches "aftermath"). The README advertised "Full RAG" and a "vector
database". This is the clearest gap between what the repository claimed and
what it did.

## Decision

`retrieve(query, n_results)` queries the ChromaDB collection with
`query_texts` — real embedding similarity. It returns a `Retrieval` carrying
the documents and a `source`: `"vector"` when the store answered,
`"keyword-fallback"` only when the embedding backend actually raised, and
`"empty"` when nothing matched. The doubt-resolver node puts that `source`
into its response, so a consumer can see which path answered.

The keyword matcher survives, but as a labelled fallback for a genuinely
unavailable backend — not as the implementation.

Nothing runs at import. The client and the one-time seed are created on first
use (`@lru_cache`), so importing the module — for a test, the API, the MCP
server — does not spin up ChromaDB.

## Consequences

A semantic query with none of the seed keywords ("how do leaves turn sunlight
into food") now retrieves the photosynthesis document; the old code returned
nothing for it. Tests exercise the real store (they are slower for it) and a
separate test forces the fallback and asserts it is labelled.
