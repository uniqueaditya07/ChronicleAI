from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.case import Case
from app.models.source import Source, SourceChunk
from app.schemas.source import SourceResponse, SourceDetailResponse, SourceListResponse, SourceChunkResponse, SourceChunkListResponse
from app.services.ingestion import IngestionService

router = APIRouter(prefix="/cases/{case_id}/sources", tags=["Sources"])

@router.post("/", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def upload_source(
    case_id: str, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    """Uploads and ingests a new evidence file for a case."""
    ingestion_service = IngestionService(db)
    source = await ingestion_service.ingest_file(case_id, file)
    
    # Calculate chunk count for response
    source.chunk_count = db.query(SourceChunk).filter(SourceChunk.source_id == source.id).count()
    return source

@router.get("/", response_model=SourceListResponse)
def list_sources(
    case_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Lists sources for a case."""
    # Validate case
    if not db.query(Case).filter(Case.id == case_id).first():
        raise HTTPException(status_code=404, detail="Case not found")
        
    query = db.query(Source).filter(Source.case_id == case_id)
    total = query.count()
    sources = query.order_by(Source.created_at.desc()).offset(skip).limit(limit).all()
    
    for s in sources:
        s.chunk_count = db.query(SourceChunk).filter(SourceChunk.source_id == s.id).count()
        
    return {"items": sources, "total": total}

@router.get("/{source_id}", response_model=SourceDetailResponse)
def get_source(
    case_id: str,
    source_id: str,
    db: Session = Depends(get_db)
):
    """Gets details of a specific source."""
    source = db.query(Source).filter(Source.case_id == case_id, Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
        
    source.chunk_count = db.query(SourceChunk).filter(SourceChunk.source_id == source.id).count()
    return source

@router.get("/{source_id}/chunks", response_model=SourceChunkListResponse)
def list_source_chunks(
    case_id: str,
    source_id: str,
    skip: int = 0,
    limit: int = 100,
    chunk_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Lists chunks for a specific source."""
    source = db.query(Source).filter(Source.case_id == case_id, Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
        
    query = db.query(SourceChunk).filter(SourceChunk.source_id == source_id)
    
    if chunk_type:
        query = query.filter(SourceChunk.chunk_type == chunk_type)
        
    total = query.count()
    chunks = query.order_by(SourceChunk.chunk_index.asc()).offset(skip).limit(limit).all()
    
    return {"items": chunks, "total": total}
