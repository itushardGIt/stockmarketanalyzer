"""Chroma-backed retrieval for explanatory portfolio knowledge."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _embeddings() -> Any:
    """Create the local Hugging Face embedding model on first use."""
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


def get_collection(persist_directory: Path, collection_name: str = "portfolio_knowledge") -> Any:
    """Return a persistent Chroma collection using local embeddings."""
    from langchain_chroma import Chroma

    persist_directory.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=collection_name,
        embedding_function=_embeddings(),
        persist_directory=str(persist_directory),
    )


def add_knowledge_texts(persist_directory: Path, texts: list[str], collection_name: str = "portfolio_knowledge") -> None:
    """Add explanatory documents to the vector store."""
    if not texts:
        return
    get_collection(persist_directory, collection_name).add_texts(texts)


def search_knowledge_base(
    query: str,
    persist_directory: Path,
    collection_name: str = "portfolio_knowledge",
    k: int = 4,
) -> list[str]:
    """Retrieve explanatory passages; never use this for portfolio numbers."""
    collection = get_collection(persist_directory, collection_name)
    return [document.page_content for document in collection.similarity_search(query, k=k)]