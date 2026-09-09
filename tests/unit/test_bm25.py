import pytest
from src.retrieval.sparse.bm25_retriever import BM25Retriever


def test_bm25_index_and_search():
    retriever = BM25Retriever()
    documents = [
        "The quick brown fox jumps over the lazy dog",
        "A fast brown fox leaps across the sleepy hound",
        "Python is a programming language",
    ]
    chunk_ids = ["c1", "c2", "c3"]
    retriever.index_documents(documents, chunk_ids)
    results = retriever.search("quick fox", top_k=2)
    assert len(results) == 2
    assert results[0][0] == "c1"
    assert isinstance(results[0][1], float)


def test_bm25_empty_search():
    retriever = BM25Retriever()
    documents = ["hello world"]
    chunk_ids = ["c1"]
    retriever.index_documents(documents, chunk_ids)
    results = retriever.search("", top_k=2)
    assert len(results) == 0


def test_bm25_save_load(tmp_path):
    retriever = BM25Retriever()
    documents = [
        "hello world python programming",
        "goodbye world java development",
        "hello python developer tools",
    ]
    chunk_ids = ["c1", "c2", "c3"]
    retriever.index_documents(documents, chunk_ids)
    index_path = str(tmp_path / "bm25.pkl")
    retriever.save(index_path)

    new_retriever = BM25Retriever()
    new_retriever.load(index_path)
    results = new_retriever.search("hello python", top_k=2)
    assert len(results) >= 1
    assert "c1" in [r[0] for r in results]


def test_bm25_search_before_index():
    retriever = BM25Retriever()
    results = retriever.search("test", top_k=1)
    assert len(results) == 0


def test_bm25_is_loaded():
    retriever = BM25Retriever()
    assert not retriever.is_loaded()
    documents = ["hello"]
    chunk_ids = ["c1"]
    retriever.index_documents(documents, chunk_ids)
    assert retriever.is_loaded()
