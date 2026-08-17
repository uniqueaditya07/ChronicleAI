from app.services.parsers.log_parser import LOGParser
from app.models.source import ChunkType

def test_log_parser_can_handle():
    parser = LOGParser()
    assert parser.can_handle("text/plain", "log")
    assert not parser.can_handle("text/plain", "txt")

def test_log_parser_parsing(tmp_path):
    parser = LOGParser()
    test_file = tmp_path / "test.log"
    content = "2026-08-18 10:00:00 INFO System started\n\n2026-08-18 10:01:00 ERROR Failure"
    test_file.write_text(content, encoding="utf-8")
    
    doc = parser.parse(test_file)
    assert len(doc.chunks) == 2
    
    assert doc.chunks[0].chunk_type == ChunkType.log_entry
    assert doc.chunks[0].content_text == "2026-08-18 10:00:00 INFO System started"
    assert doc.chunks[0].metadata["line_number"] == 1
    
    assert doc.chunks[1].chunk_type == ChunkType.log_entry
    assert doc.chunks[1].content_text == "2026-08-18 10:01:00 ERROR Failure"
    assert doc.chunks[1].metadata["line_number"] == 3  # Blank line was line 2
