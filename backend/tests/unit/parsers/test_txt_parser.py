from app.services.parsers.txt_parser import TXTParser
from app.models.source import ChunkType

def test_txt_parser_can_handle():
    parser = TXTParser()
    assert parser.can_handle("text/plain", "txt")
    assert not parser.can_handle("application/pdf", "pdf")

def test_txt_parser_parsing(tmp_path):
    parser = TXTParser()
    test_file = tmp_path / "test.txt"
    content = "Paragraph 1 line 1.\nParagraph 1 line 2.\n\nParagraph 2."
    test_file.write_text(content, encoding="utf-8")
    
    doc = parser.parse(test_file)
    assert len(doc.chunks) == 2
    
    assert doc.chunks[0].chunk_type == ChunkType.paragraph
    assert doc.chunks[0].content_text == "Paragraph 1 line 1.\nParagraph 1 line 2."
    assert doc.chunks[0].start_offset == 0
    assert doc.chunks[0].end_offset == len("Paragraph 1 line 1.\nParagraph 1 line 2.")
    
    assert doc.chunks[1].chunk_type == ChunkType.paragraph
    assert doc.chunks[1].content_text == "Paragraph 2."
    
def test_txt_parser_fallback_encoding(tmp_path):
    parser = TXTParser()
    test_file = tmp_path / "test_latin1.txt"
    # Write some non-utf-8 bytes
    test_file.write_bytes(b"Paragraph 1 with \xe9.")
    
    doc = parser.parse(test_file)
    assert len(doc.chunks) == 1
    assert doc.chunks[0].content_text == "Paragraph 1 with \xe9."
