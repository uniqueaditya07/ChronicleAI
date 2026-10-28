from typing import Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Case, EvidenceFile
from app.schemas import (
    CaseEntitiesResponse,
    CaseEntitiesSummaryResponse,
    GroupedEntity,
    EntityOccurrence
)
from app.ner import (
    extract_entities_from_file,
    group_and_sort_entities,
    get_spacy_model,
    SUPPORTED_LABEL_MAP
)

router = APIRouter(prefix="/api/cases/{case_id}/entities", tags=["entities"])

def get_verified_case(case_id: int, db: Session) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID {case_id} not found."
        )
    return case

@router.get("", response_model=CaseEntitiesResponse)
def get_case_entities(
    case_id: int,
    category: Optional[str] = Query(None, description="Optional category filter (e.g. Person, Organization, Location, Date)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Grouped entities per page"),
    db: Session = Depends(get_db)
):
    # 1. Verify case exists
    get_verified_case(case_id, db)

    # 2. Ensure spaCy model is loadable (raises 503 if missing)
    nlp = get_spacy_model()

    # 3. Retrieve only evidence files for this case
    evidence_files = (
        db.query(EvidenceFile)
        .filter(EvidenceFile.case_id == case_id)
        .order_by(EvidenceFile.original_filename.asc(), EvidenceFile.id.asc())
        .all()
    )

    # 4. Extract entities across all evidence files in this case
    all_occurrences: list[EntityOccurrence] = []
    for file_record in evidence_files:
        file_occs = extract_entities_from_file(file_record, nlp=nlp)
        all_occurrences.extend(file_occs)

    # 5. Group and sort
    all_grouped = group_and_sort_entities(all_occurrences)

    # 6. Compute global category counts for case
    category_counts: Dict[str, int] = {
        "Person": 0,
        "Organization": 0,
        "Location": 0,
        "Date": 0
    }
    for g in all_grouped:
        if g.category in category_counts:
            category_counts[g.category] += 1
        else:
            category_counts[g.category] = 1

    # 7. Apply optional category filter
    filtered_grouped = all_grouped
    if category:
        cat_clean = category.strip().lower()
        filtered_grouped = [g for g in all_grouped if g.category.lower() == cat_clean]

    total_groups = len(filtered_grouped)
    total_occurrences = sum(g.count for g in filtered_grouped)

    # 8. Deterministic pagination
    offset = (page - 1) * page_size
    paged_entities = filtered_grouped[offset : offset + page_size]

    return CaseEntitiesResponse(
        case_id=case_id,
        total_groups=total_groups,
        total_occurrences=total_occurrences,
        page=page,
        page_size=page_size,
        category_counts=category_counts,
        entities=paged_entities
    )

@router.get("/summary", response_model=CaseEntitiesSummaryResponse)
def get_case_entities_summary(
    case_id: int,
    db: Session = Depends(get_db)
):
    # 1. Verify case exists
    get_verified_case(case_id, db)

    # 2. Ensure spaCy model is loadable
    nlp = get_spacy_model()

    # 3. Retrieve evidence files for this case
    evidence_files = (
        db.query(EvidenceFile)
        .filter(EvidenceFile.case_id == case_id)
        .order_by(EvidenceFile.original_filename.asc(), EvidenceFile.id.asc())
        .all()
    )

    all_occurrences: list[EntityOccurrence] = []
    for file_record in evidence_files:
        all_occurrences.extend(extract_entities_from_file(file_record, nlp=nlp))

    all_grouped = group_and_sort_entities(all_occurrences)

    category_counts: Dict[str, int] = {
        "Person": 0,
        "Organization": 0,
        "Location": 0,
        "Date": 0
    }
    for g in all_grouped:
        if g.category in category_counts:
            category_counts[g.category] += 1
        else:
            category_counts[g.category] = 1

    return CaseEntitiesSummaryResponse(
        case_id=case_id,
        total_unique_entities=len(all_grouped),
        total_occurrences=len(all_occurrences),
        category_counts=category_counts,
        evidence_files_processed=len(evidence_files)
    )
