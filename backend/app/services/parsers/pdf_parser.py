import pymupdf as fitz
from pathlib import Path
from typing import Dict, Any
from app.services.parsers.base import BaseParser
from app.schemas.source import ParsedDocument, ParsedChunk
from app.models.source import ChunkType

class PDFParser(BaseParser):
    def can_handle(self, file_type: str, extension: str) -> bool:
        return extension.lower() == "pdf"

    def parse(self, file_path: Path, metadata: Dict[str, Any] = None) -> ParsedDocument:
        try:
            doc = fitz.open(file_path)
        except Exception as e:
            raise ValueError(f"Invalid PDF: {e}")

        chunks = []
        has_extractable_text = False
        
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            blocks = page.get_text("blocks")
            
            page_has_text = False
            for b in blocks:
                # b is a tuple: (x0, y0, x1, y1, text, block_no, block_type)
                # block_type 0 means text
                if b[6] == 0:
                    text = b[4].strip()
                    if text:
                        page_has_text = True
                        has_extractable_text = True
                        chunks.append(
                            ParsedChunk(
                                chunk_type=ChunkType.paragraph,
                                content_text=text,
                                page_number=page_num + 1,
                                metadata={
                                    "bbox": [b[0], b[1], b[2], b[3]]
                                }
                            )
                        )
            
            if not page_has_text:
                chunks.append(
                    ParsedChunk(
                        chunk_type=ChunkType.page,
                        content_text="",
                        page_number=page_num + 1,
                        metadata={"has_extractable_text": False}
                    )
                )

        page_count = len(doc)
        doc.close()
        return ParsedDocument(
            chunks=chunks, 
            metadata={"has_extractable_text": has_extractable_text, "page_count": page_count}
        )
