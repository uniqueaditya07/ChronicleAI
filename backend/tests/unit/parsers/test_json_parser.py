from app.services.parsers.json_parser import JSONParser
from app.models.source import ChunkType

def test_json_parser_can_handle():
    parser = JSONParser()
    assert parser.can_handle("application/json", "json")
    assert not parser.can_handle("text/plain", "txt")

def test_json_parser_parsing_dict(tmp_path):
    parser = JSONParser()
    test_file = tmp_path / "test.json"
    content = '{"user": {"name": "Alice", "age": 30}}'
    test_file.write_text(content, encoding="utf-8")
    
    doc = parser.parse(test_file)
    assert len(doc.chunks) == 2
    
    assert doc.chunks[0].chunk_type == ChunkType.row
    assert doc.chunks[0].content_text == "user.name: Alice"
    assert doc.chunks[0].metadata["json_path"] == "user.name"
    
    assert doc.chunks[1].content_text == "user.age: 30"
    assert doc.chunks[1].metadata["json_path"] == "user.age"

def test_json_parser_parsing_array(tmp_path):
    parser = JSONParser()
    test_file = tmp_path / "test_arr.json"
    content = '[{"id": 1}, {"id": 2}]'
    test_file.write_text(content, encoding="utf-8")
    
    doc = parser.parse(test_file)
    assert len(doc.chunks) == 2
    
    assert doc.chunks[0].content_text == "[0].id: 1"
    assert doc.chunks[0].metadata["json_path"] == "[0].id"
    
    assert doc.chunks[1].content_text == "[1].id: 2"
