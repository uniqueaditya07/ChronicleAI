from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, ConfigDict, Field
from app.models.source import ProcessingStatus, ChunkType

class SourceChunkBase(BaseModel):
    chunk_type: ChunkType
    chunk_index: int
    content_text: str
    page_number: Optional[int] = None
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    metadata_json: Optional[str] = None

class SourceChunkResponse(SourceChunkBase):
    id: str
    source_id: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class SourceChunkListResponse(BaseModel):
    items: List[SourceChunkResponse]
    total: int

class SourceBase(BaseModel):
    case_id: str
    original_filename: str
    file_type: str
    file_size: int
    content_hash: str
    processing_status: ProcessingStatus
    processing_error: Optional[str] = None
    metadata_json: Optional[str] = None

class SourceResponse(SourceBase):
    id: str
    created_at: datetime
    updated_at: datetime
    chunk_count: int = 0
    
    model_config = ConfigDict(from_attributes=True)

class SourceDetailResponse(SourceResponse):
    pass # No chunks here, chunks are fetched via paginated endpoint

class SourceListResponse(BaseModel):
    items: List[SourceResponse]
    total: int

# Intermediate models for parser subsystem (Not returned directly by API)
class ParsedChunk(BaseModel):
    chunk_type: ChunkType
    content_text: str
    page_number: Optional[int] = None
    start_offset: Optional[int] = None
    end_offset: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

class ParsedDocument(BaseModel):
    chunks: List[ParsedChunk]
    metadata: Optional[Dict[str, Any]] = None
