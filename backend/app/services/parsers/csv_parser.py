import pandas as pd
from pathlib import Path
from typing import Dict, Any
from app.services.parsers.base import BaseParser
from app.schemas.source import ParsedDocument, ParsedChunk
from app.models.source import ChunkType

class CSVParser(BaseParser):
    def can_handle(self, file_type: str, extension: str) -> bool:
        return extension.lower() == "csv"

    def parse(self, file_path: Path, metadata: Dict[str, Any] = None) -> ParsedDocument:
        try:
            # Read deterministically, treat all as string to avoid type coercion loss
            df = pd.read_csv(file_path, dtype=str)
        except Exception as e:
            raise ValueError(f"Invalid CSV: {e}")

        chunks = []
        headers = df.columns.tolist()
        
        for i, row in df.iterrows():
            row_dict = row.dropna().to_dict()
            if not row_dict:
                continue
                
            # Format row as key: value list for deterministic text representation
            content_lines = []
            for col in headers:
                if col in row_dict:
                    content_lines.append(f"{col}: {row_dict[col]}")
                    
            if content_lines:
                chunks.append(
                    ParsedChunk(
                        chunk_type=ChunkType.row,
                        content_text="\n".join(content_lines),
                        metadata={"row_number": i + 2} # 1-indexed, +1 for header
                    )
                )

        return ParsedDocument(chunks=chunks, metadata={"headers": headers})
