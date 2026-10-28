from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Case, EvidenceFile, EvidenceLine
from app.schemas import SearchResponse, SearchResultItem

router = APIRouter(prefix="/api/cases/{case_id}/search", tags=["search"])

def escape_like_literal(query_str: str) -> str:
    """
    Escapes SQL LIKE wildcards '%' and '_' using '\\' as escape character.
    This guarantees exact literal substring matching.
    """
    return query_str.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

@router.get("", response_model=SearchResponse)
def search_case_evidence(
    case_id: int,
    q: str = Query(..., min_length=1, max_length=500, description="Search term or phrase"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=200, description="Items per page"),
    db: Session = Depends(get_db)
):
    # 1. Reject empty or whitespace-only queries
    cleaned_query = q.strip()
    if not cleaned_query:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Search query cannot be empty or contain only whitespace."
        )

    # 2. Verify case exists (return 404 if nonexistent)
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID {case_id} not found."
        )

    # 3. Construct case-scoped search query
    # Escape LIKE wildcards so %, _ and \ are treated literally
    escaped_query = escape_like_literal(cleaned_query)
    like_pattern = f"%{escaped_query}%"

    # Base join query: EvidenceLine -> EvidenceFile -> Case
    base_query = (
        db.query(
            EvidenceLine.id,
            EvidenceLine.line_number,
            EvidenceLine.content.label("line_content"),
            EvidenceFile.id.label("evidence_file_id"),
            EvidenceFile.original_filename,
            EvidenceFile.sha256_hash,
            EvidenceFile.case_id
        )
        .join(EvidenceFile, EvidenceLine.evidence_file_id == EvidenceFile.id)
        .filter(EvidenceFile.case_id == case_id)
        .filter(EvidenceLine.content.ilike(like_pattern, escape="\\"))
    )

    # Total match count
    total_matches = base_query.count()

    # Deterministic ordering: evidence filename ASC, evidence ID ASC, line number ASC
    offset = (page - 1) * page_size
    records = (
        base_query
        .order_by(
            EvidenceFile.original_filename.asc(),
            EvidenceFile.id.asc(),
            EvidenceLine.line_number.asc()
        )
        .offset(offset)
        .limit(page_size)
        .all()
    )

    results = [
        SearchResultItem(
            case_id=record.case_id,
            evidence_file_id=record.evidence_file_id,
            original_filename=record.original_filename,
            sha256_hash=record.sha256_hash,
            line_number=record.line_number,
            line_content=record.line_content
        )
        for record in records
    ]

    return SearchResponse(
        query=cleaned_query,
        case_id=case_id,
        total_matches=total_matches,
        page=page,
        page_size=page_size,
        results=results
    )
