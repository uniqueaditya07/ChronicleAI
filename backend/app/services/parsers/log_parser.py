from pathlib import Path
from typing import Dict, Any, List
from app.services.parsers.base import BaseParser
from app.schemas.source import ParsedDocument, ParsedChunk
from app.models.source import ChunkType

class LOGParser(BaseParser):
    def can_handle(self, file_type: str, extension: str) -> bool:
        return extension.lower() == "log"

    def parse(self, file_path: Path, metadata: Dict[str, Any] = None) -> ParsedDocument:
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = file_path.read_text(encoding="latin-1")

        chunks = []
        lines = content.splitlines(keepends=True)
        
        current_offset = 0
        for i, line in enumerate(lines):
            line_len = len(line)
            clean_line = line.strip()
            if clean_line:
                chunks.append(
                    ParsedChunk(
                        chunk_type=ChunkType.log_entry,
                        content_text=clean_line,
                        start_offset=current_offset,
                        end_offset=current_offset + len(clean_line),
                        metadata={"line_number": i + 1}
                    )
                )
            current_offset += line_len

        return ParsedDocument(chunks=chunks)
