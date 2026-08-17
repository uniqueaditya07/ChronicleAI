from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.case import Case
from app.schemas.case import (
    CaseCreate,
    CaseUpdate,
    CaseResponse,
    CaseListResponse,
)

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.post(
    "",
    response_model=CaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new case",
)
def create_case(
    case_in: CaseCreate,
    db: Session = Depends(get_db),
) -> Case:
    new_case = Case(
        name=case_in.name,
        description=case_in.description,
        status="active",
    )
    db.add(new_case)
    db.commit()
    db.refresh(new_case)
    return new_case


@router.get(
    "",
    response_model=CaseListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all cases",
)
def list_cases(
    skip: int = 0,
    limit: int = 50,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
) -> CaseListResponse:
    query = select(Case)
    if status_filter:
        query = query.where(Case.status == status_filter)

    total_query = select(func.count()).select_from(query.subquery())
    total = db.scalar(total_query) or 0

    items = db.scalars(
        query.order_by(Case.created_at.desc()).offset(skip).limit(limit)
    ).all()

    return CaseListResponse(items=list(items), total=total)


@router.get(
    "/{case_id}",
    response_model=CaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Get case details",
)
def get_case(
    case_id: str,
    db: Session = Depends(get_db),
) -> Case:
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID '{case_id}' not found.",
        )
    return case


@router.patch(
    "/{case_id}",
    response_model=CaseResponse,
    status_code=status.HTTP_200_OK,
    summary="Update case",
)
def update_case(
    case_id: str,
    case_update: CaseUpdate,
    db: Session = Depends(get_db),
) -> Case:
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID '{case_id}' not found.",
        )

    if case_update.name is not None:
        case.name = case_update.name
    if case_update.description is not None:
        case.description = case_update.description
    if case_update.status is not None:
        case.status = case_update.status

    db.commit()
    db.refresh(case)
    return case


@router.delete(
    "/{case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete case",
)
def delete_case(
    case_id: str,
    db: Session = Depends(get_db),
) -> None:
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID '{case_id}' not found.",
        )
    db.delete(case)
    db.commit()
