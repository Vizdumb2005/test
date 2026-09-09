import pytest
from src.ingestion.chunking.strategies import Chunker, get_strategy
from src.core.models import Document


def _make_doc(text: str, doc_id: str = "doc_1") -> Document:
    return Document(
        document_id=doc_id,
        source="test",
        file_name="test.txt",
        document_type="text",
        text=text,
    )


def test_chunker_fixed_basic():
    doc = _make_doc("A" * 2500)
    chunker = Chunker(chunk_size=1000, chunk_overlap=200, strategy="fixed")
    chunks = chunker.chunk(doc)
    assert len(chunks) > 1
    assert all(len(c.text) <= 1000 for c in chunks)


def test_chunker_fixed_small():
    doc = _make_doc("Hello world")
    chunker = Chunker(chunk_size=100, chunk_overlap=20, strategy="fixed")
    chunks = chunker.chunk(doc)
    assert len(chunks) == 1


def test_chunker_fixed_overlap():
    doc = _make_doc("A" * 2500)
    chunker = Chunker(chunk_size=1000, chunk_overlap=200, strategy="fixed")
    chunks = chunker.chunk(doc)
    for i in range(len(chunks) - 1):
        if len(chunks[i].text) >= 200 and len(chunks[i + 1].text) >= 200:
            overlap_start = chunks[i].text[-200:]
            next_start = chunks[i + 1].text[:200]
            assert overlap_start == next_start


def test_chunker_recursive_basic():
    doc = _make_doc("Paragraph one.\n\nParagraph two.\n\nParagraph three.")
    chunker = Chunker(chunk_size=100, chunk_overlap=20, strategy="recursive")
    chunks = chunker.chunk(doc)
    assert len(chunks) >= 1


def test_chunker_recursive_empty():
    doc = _make_doc("")
    chunker = Chunker(chunk_size=100, chunk_overlap=20, strategy="recursive")
    chunks = chunker.chunk(doc)
    assert chunks == []


def test_chunker_recursive_single_paragraph():
    text = "This is a single paragraph that is long enough to be split into multiple chunks when the chunk size is small enough for the recursive algorithm to handle it properly."
    doc = _make_doc(text)
    chunker = Chunker(chunk_size=50, chunk_overlap=10, strategy="recursive")
    chunks = chunker.chunk(doc)
    assert len(chunks) > 1


def test_chunker_sentence_aware():
    doc = _make_doc("First sentence. Second sentence. Third sentence.")
    chunker = Chunker(chunk_size=50, chunk_overlap=10, strategy="sentence")
    chunks = chunker.chunk(doc)
    assert len(chunks) >= 1


def test_chunker_paragraph_aware():
    doc = _make_doc("Para one.\n\nPara two.\n\nPara three.")
    chunker = Chunker(chunk_size=100, chunk_overlap=20, strategy="paragraph")
    chunks = chunker.chunk(doc)
    assert len(chunks) >= 1


def test_chunker_metadata():
    doc = _make_doc("Hello world test")
    chunker = Chunker(chunk_size=5, chunk_overlap=1, strategy="fixed")
    chunks = chunker.chunk(doc)
    assert len(chunks) > 0
    assert chunks[0].chunk_id == f"{doc.document_id}_chunk_0000"
    assert chunks[0].document_id == doc.document_id
    assert "chunking_strategy" in chunks[0].metadata


def test_get_strategy_unknown():
    with pytest.raises(ValueError):
        get_strategy("unknown_strategy")
