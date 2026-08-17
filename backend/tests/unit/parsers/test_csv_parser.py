import pandas as pd
from app.services.parsers.csv_parser import CSVParser
from app.models.source import ChunkType

def test_csv_parser_can_handle():
    parser = CSVParser()
    assert parser.can_handle("text/csv", "csv")
    assert not parser.can_handle("application/json", "json")

def test_csv_parser_parsing(tmp_path):
    parser = CSVParser()
    test_file = tmp_path / "test.csv"
    content = "Name,Age,Role\nAlice,30,Engineer\nBob,,Designer\n"
    test_file.write_text(content, encoding="utf-8")
    
    doc = parser.parse(test_file)
    assert doc.metadata["headers"] == ["Name", "Age", "Role"]
    
    assert len(doc.chunks) == 2
    
    assert doc.chunks[0].chunk_type == ChunkType.row
    assert doc.chunks[0].content_text == "Name: Alice\nAge: 30\nRole: Engineer"
    assert doc.chunks[0].metadata["row_number"] == 2
    
    assert doc.chunks[1].chunk_type == ChunkType.row
    assert doc.chunks[1].content_text == "Name: Bob\nRole: Designer"  # Empty cell skipped
    assert doc.chunks[1].metadata["row_number"] == 3

def test_csv_parser_empty(tmp_path):
    parser = CSVParser()
    test_file = tmp_path / "empty.csv"
    test_file.write_text("Name,Age\n", encoding="utf-8")
    
    doc = parser.parse(test_file)
    assert len(doc.chunks) == 0
