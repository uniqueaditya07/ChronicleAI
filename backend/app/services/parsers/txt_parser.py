from pathlib import Path
from typing import Dict, Any, List
from app.services.parsers.base import BaseParser
from app.schemas.source import ParsedDocument, ParsedChunk
from app.models.source import ChunkType

class TXTParser(BaseParser):
    def can_handle(self, file_type: str, extension: str) -> bool:
        return extension.lower() == "txt"

    def parse(self, file_path: Path, metadata: Dict[str, Any] = None) -> ParsedDocument:
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Fallback for non-utf-8
            content = file_path.read_text(encoding="latin-1")

        chunks = []
        paragraphs = content.split("\n\n")
        
        current_offset = 0
        for i, para in enumerate(paragraphs):
            para = para.strip()
            if not para:
                current_offset += len("\n\n")
                continue
                
            start = content.find(para, current_offset)
            end = start + len(para)
            current_offset = end
            
            chunks.append(
                ParsedChunk(
                    chunk_type=ChunkType.paragraph,
                    content_text=para,
                    start_offset=start,
                    end_offset=end
                )
            )

        return ParsedDocument(chunks=chunks)
