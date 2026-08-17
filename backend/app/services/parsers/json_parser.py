import json
from pathlib import Path
from typing import Dict, Any, List
from app.services.parsers.base import BaseParser
from app.schemas.source import ParsedDocument, ParsedChunk
from app.models.source import ChunkType

class JSONParser(BaseParser):
    def can_handle(self, file_type: str, extension: str) -> bool:
        return extension.lower() == "json"

    def _extract_chunks(self, data: Any, current_path: str, chunks: List[ParsedChunk]):
        if isinstance(data, dict):
            for k, v in data.items():
                new_path = f"{current_path}.{k}" if current_path else k
                self._extract_chunks(v, new_path, chunks)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_path = f"{current_path}[{i}]"
                self._extract_chunks(item, new_path, chunks)
        else:
            # It's a leaf node
            content = f"{current_path}: {data}" if current_path else str(data)
            chunks.append(
                ParsedChunk(
                    chunk_type=ChunkType.row, # Using row to represent a record/leaf
                    content_text=content,
                    metadata={"json_path": current_path}
                )
            )

    def parse(self, file_path: Path, metadata: Dict[str, Any] = None) -> ParsedDocument:
        content = file_path.read_text(encoding="utf-8")
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")

        chunks = []
        self._extract_chunks(data, "", chunks)

        return ParsedDocument(chunks=chunks)
