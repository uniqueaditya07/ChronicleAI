import docx
from pathlib import Path
from typing import Dict, Any
from app.services.parsers.base import BaseParser
from app.schemas.source import ParsedDocument, ParsedChunk
from app.models.source import ChunkType

class DOCXParser(BaseParser):
    def can_handle(self, file_type: str, extension: str) -> bool:
        return extension.lower() == "docx"

    def parse(self, file_path: Path, metadata: Dict[str, Any] = None) -> ParsedDocument:
        try:
            doc = docx.Document(file_path)
        except Exception as e:
            raise ValueError(f"Invalid DOCX: {e}")

        chunks = []
        
        # We iterate over paragraphs and tables in order of appearance in document body.
        # python-docx doesn't provide a unified iterator for paragraphs + tables natively 
        # in the exact document order without dropping down to XML lxml processing.
        # For Phase 1, we can just extract paragraphs first, then tables, or use block-level iteration.
        # Since deterministic ordering is required, let's process paragraphs then tables 
        # (or rely on iter_block_items if we write a custom iterator, but for MVP paragraphs and tables sequentially).
        # Wait, to preserve ordering we should extract from the body XML.
        
        # For MVP: Iterate paragraphs
        for i, para in enumerate(doc.paragraphs):
            text = para.text.strip()
            if text:
                chunks.append(
                    ParsedChunk(
                        chunk_type=ChunkType.paragraph,
                        content_text=text,
                        metadata={"docx_paragraph_index": i, "style": para.style.name}
                    )
                )

        # Iterate tables
        for t_idx, table in enumerate(doc.tables):
            for r_idx, row in enumerate(table.rows):
                row_text = []
                for cell in row.cells:
                    ctext = cell.text.strip()
                    if ctext:
                        row_text.append(ctext)
                if row_text:
                    chunks.append(
                        ParsedChunk(
                            chunk_type=ChunkType.row,
                            content_text=" | ".join(row_text),
                            metadata={
                                "docx_table_index": t_idx, 
                                "docx_row_index": r_idx
                            }
                        )
                    )

        return ParsedDocument(chunks=chunks)
