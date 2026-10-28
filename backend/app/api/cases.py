from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models import Case, CaseStatus
from app.schemas import CaseCreate, CaseUpdate, CaseResponse, CaseStatsResponse

router = APIRouter(prefix="/api/cases", tags=["cases"])

@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(case_in: CaseCreate, db: Session = Depends(get_db)):
    # Check for existing case_number
    existing_case = db.query(Case).filter(Case.case_number == case_in.case_number.strip()).first()
    if existing_case:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Case with case number '{case_in.case_number.strip()}' already exists."
        )

    db_case = Case(
        case_number=case_in.case_number.strip(),
        title=case_in.title.strip(),
        description=case_in.description.strip() if case_in.description else None,
        status=case_in.status
    )
    db.add(db_case)
    try:
        db.commit()
        db.refresh(db_case)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Case with case number '{case_in.case_number.strip()}' already exists."
        )
    return db_case

@router.get("", response_model=List[CaseResponse])
def list_cases(
    status_filter: Optional[CaseStatus] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Case)
    if status_filter:
        query = query.filter(Case.status == status_filter)
    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.filter(
            (Case.case_number.ilike(search_pattern)) | (Case.title.ilike(search_pattern))
        )
    cases = query.order_by(Case.created_at.desc()).all()
    return cases

@router.get("/stats", response_model=CaseStatsResponse)
def get_case_stats(db: Session = Depends(get_db)):
    total = db.query(Case).count()
    open_count = db.query(Case).filter(Case.status == CaseStatus.OPEN).count()
    in_progress = db.query(Case).filter(Case.status == CaseStatus.IN_PROGRESS).count()
    closed = db.query(Case).filter(Case.status == CaseStatus.CLOSED).count()

    return CaseStatsResponse(
        total_cases=total,
        open_cases=open_count,
        in_progress_cases=in_progress,
        closed_cases=closed
    )

@router.get("/{case_id}", response_model=CaseResponse)
def get_case(case_id: int, db: Session = Depends(get_db)):
    db_case = db.query(Case).filter(Case.id == case_id).first()
    if not db_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID {case_id} not found."
        )
    return db_case

@router.patch("/{case_id}", response_model=CaseResponse)
def update_case(case_id: int, case_update: CaseUpdate, db: Session = Depends(get_db)):
    db_case = db.query(Case).filter(Case.id == case_id).first()
    if not db_case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID {case_id} not found."
        )

    update_data = case_update.model_dump(exclude_unset=True)
    if not update_data:
        return db_case

    for field, value in update_data.items():
        if field == "title" and value is not None:
            setattr(db_case, field, value.strip())
        elif field == "description" and value is not None:
            setattr(db_case, field, value.strip())
        elif value is not None:
            setattr(db_case, field, value)

    db.commit()
    db.refresh(db_case)
    return db_case
