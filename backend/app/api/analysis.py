from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AnalysisResponse
from app.analysis_service import run_case_analysis

router = APIRouter(prefix="/api/cases/{case_id}/analysis", tags=["analysis"])

@router.post("", response_model=AnalysisResponse, status_code=status.HTTP_200_OK)
def trigger_case_analysis(
    case_id: int,
    db: Session = Depends(get_db)
):
    """
    Perform on-demand, evidence-grounded case analysis using Gemini.
    Validates all citations against indexed line numbers and filters unverified claims.
    Requires GEMINI_API_KEY to be configured in the environment.
    """
    return run_case_analysis(case_id=case_id, db=db)
