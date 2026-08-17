import pymupdf as fitz
from app.services.parsers.pdf_parser import PDFParser
from app.models.source import ChunkType

def test_pdf_parser_can_handle():
    parser = PDFParser()
    assert parser.can_handle("application/pdf", "pdf")
    assert not parser.can_handle("text/plain", "txt")

def test_pdf_parser_parsing(tmp_path):
    # Create a small valid PDF using fitz
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Test paragraph 1")
    page.insert_text((50, 100), "Test paragraph 2")
    
    # Add a blank page
    doc.new_page()
    
    test_file = tmp_path / "test.pdf"
    doc.save(str(test_file))
    doc.close()

    parser = PDFParser()
    parsed_doc = parser.parse(test_file)
    
    assert parsed_doc.metadata["page_count"] == 2
    assert parsed_doc.metadata["has_extractable_text"] is True
    
    # We expect 2 chunks on page 1, 1 empty chunk on page 2
    assert len(parsed_doc.chunks) >= 3
    
    # The exact block chunks may vary depending on how fitz groups them, but we should find both texts
    texts = [c.content_text for c in parsed_doc.chunks]
    assert any("Test paragraph 1" in t for t in texts)
    assert any("Test paragraph 2" in t for t in texts)
    
    # Check page 2 empty chunk
    empty_chunk = next((c for c in parsed_doc.chunks if c.page_number == 2), None)
    assert empty_chunk is not None
    assert empty_chunk.chunk_type == ChunkType.page
    assert empty_chunk.content_text == ""
    assert empty_chunk.metadata["has_extractable_text"] is False
