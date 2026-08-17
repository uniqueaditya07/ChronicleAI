import json
from typing import List
from app.schemas.source import ParsedDocument, ParsedChunk
from app.models.source import SourceChunk, ChunkType

class DocumentChunker:
    def chunk_document(self, source_id: str, parsed_doc: ParsedDocument) -> List[SourceChunk]:
        """
        Converts ParsedDocument (from a Parser) into a list of SourceChunk ORM models.
        Preserves deterministic ordering and metadata.
        """
        source_chunks = []
        
        for index, parsed_chunk in enumerate(parsed_doc.chunks):
            # Serialize metadata safely
            meta_json = None
            if parsed_chunk.metadata:
                try:
                    meta_json = json.dumps(parsed_chunk.metadata)
                except Exception:
                    pass

            chunk = SourceChunk(
                source_id=source_id,
                chunk_type=parsed_chunk.chunk_type,
                chunk_index=index,
                content_text=parsed_chunk.content_text,
                page_number=parsed_chunk.page_number,
                start_offset=parsed_chunk.start_offset,
                end_offset=parsed_chunk.end_offset,
                metadata_json=meta_json
            )
            source_chunks.append(chunk)
            
        return source_chunks
