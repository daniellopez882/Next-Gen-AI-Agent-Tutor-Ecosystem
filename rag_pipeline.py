"""
Retrieval over the curriculum vector store.

The previous module was the repository's clearest case of a claim the code did
not keep. It built a real ChromaDB persistent client, seeded it with four
documents and their embeddings -- and then ``retrieve_context`` **ignored the
vector store entirely** and did substring keyword matching over a hardcoded
copy of the same four sentences:

    # Since ONNX inference is sometimes unstable on certain Windows
    # environments, we use a highly reliable keyword-based RAG fallback ...
    if "photosynthesis" in query_lower or "plant" in query_lower:
        matched.append(fallback_docs[0])

So the "vector database" was seeded and never queried; the retrieval was
`"math" in query`, which also matches "aftermath". The README advertised
"Full RAG".

This module actually queries ChromaDB. Keyword matching remains, but only as
an explicit, labelled fallback for when the embedding backend is genuinely
unavailable -- and ``retrieve_context`` reports which path answered. Nothing
runs at import: the client and the seed are created on first use.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from config import settings

logger = logging.getLogger("lumina.rag")

COLLECTION = "tutor_curriculum"

SEED_DOCUMENTS = [
    (
        "Photosynthesis is the process by which green plants and some other organisms use "
        "sunlight to synthesize nutrients from carbon dioxide and water, using the green "
        "pigment chlorophyll and generating oxygen as a byproduct.",
        {"subject": "Biology", "topic": "Photosynthesis", "grade": "6-8"},
    ),
    (
        "A fraction represents a part of a whole or any number of equal parts, written as a "
        "numerator over a denominator. 3/4 means three parts out of four equal parts.",
        {"subject": "Mathematics", "topic": "Fractions", "grade": "3-5"},
    ),
    (
        "The Solar System is the gravitationally bound system of the Sun and the objects that "
        "orbit it, including eight planets: Mercury, Venus, Earth, Mars, Jupiter, Saturn, "
        "Uranus and Neptune.",
        {"subject": "Science", "topic": "Astronomy", "grade": "6-8"},
    ),
    (
        "Newton's First Law of Motion states that an object remains at rest or in uniform "
        "motion in a straight line unless acted upon by an external force -- the law of inertia.",
        {"subject": "Physics", "topic": "Classical Mechanics", "grade": "9-12"},
    ),
]

# Keyword -> seed index, for the fallback only.
_KEYWORDS = {
    0: ("photosynthesis", "chlorophyll", "plant"),
    1: ("fraction", "numerator", "denominator"),
    2: ("solar system", "planet", "astronomy", "orbit"),
    3: ("newton", "inertia", "motion", "force"),
}


@dataclass(frozen=True)
class Retrieval:
    documents: list[str]
    source: str  # "vector" | "keyword-fallback" | "empty"


@lru_cache(maxsize=1)
def _collection() -> Any:
    """The ChromaDB collection, created and seeded once, on first use."""
    import chromadb

    client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
    collection = client.get_or_create_collection(
        name=COLLECTION, metadata={"hnsw:space": "cosine"}
    )
    if collection.count() == 0:
        collection.add(
            documents=[doc for doc, _ in SEED_DOCUMENTS],
            metadatas=[meta for _, meta in SEED_DOCUMENTS],
            ids=[f"curr_{i}" for i in range(len(SEED_DOCUMENTS))],
        )
        logger.info(
            "seeded %d curriculum chunks into ChromaDB at %s",
            len(SEED_DOCUMENTS),
            settings.CHROMA_PATH,
        )
    return collection


def _keyword_fallback(query: str, n_results: int) -> list[str]:
    lowered = query.lower()
    hits = [
        SEED_DOCUMENTS[i][0]
        for i, words in _KEYWORDS.items()
        if any(w in lowered for w in words)
    ]
    return hits[:n_results]


def retrieve(query: str, n_results: int = 2) -> Retrieval:
    """
    Query the vector store. Falls back to keyword matching only if the
    embedding backend raises, and says which path answered.
    """
    if not query or not query.strip():
        return Retrieval([], "empty")
    try:
        result = _collection().query(query_texts=[query], n_results=n_results)
        documents = (result.get("documents") or [[]])[0]
        if documents:
            return Retrieval(list(documents), "vector")
    except Exception:
        logger.warning("vector query failed; using the keyword fallback", exc_info=True)
        fallback = _keyword_fallback(query, n_results)
        if fallback:
            return Retrieval(fallback, "keyword-fallback")
    return Retrieval([], "empty")


def retrieve_context(query: str, n_results: int = 2) -> list[str]:
    """Documents only, for callers that do not need the source. Kept for the old name."""
    hits = retrieve(query, n_results).documents
    return hits or ["No curriculum context matched this query."]
