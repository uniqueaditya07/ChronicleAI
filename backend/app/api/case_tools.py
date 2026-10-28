from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ChatRequest, ChatResponse, AnalysisEvidenceScope, TimelineResponse, ReportRequest
from app.models import EvidenceFile
from app.analysis_service import run_case_analysis, get_gemini_model
from app.case_tools import require_case, build_timeline, build_report

router = APIRouter(prefix="/api/cases/{case_id}", tags=["case tools"])


@router.post("/chat", response_model=ChatResponse)
def chat(case_id: int, request: ChatRequest, db: Session = Depends(get_db)):
    require_case(case_id, db)
    try:
        questions = [request.question] + [turn.question for turn in request.history]
        if any(not question.strip() for question in questions):
            raise ValueError("Blank question")
        for question in questions:
            question.encode("utf-8", errors="strict")
        if any(turn.case_id != case_id for turn in request.history):
            raise ValueError("Foreign conversation")
    except ValueError:
        raise HTTPException(422, "Questions must be valid text and conversation history must belong to this case.") from None
    files = db.query(EvidenceFile).filter(EvidenceFile.case_id == case_id).all()
    if not files or not any(file.line_count for file in files):
        return ChatResponse(case_id=case_id, model_used=get_gemini_model(),
            evidence_scope=AnalysisEvidenceScope(file_count=len(files), line_count=0, total_characters=0),
            answer_status="insufficient_evidence", message="The indexed evidence does not support an answer. Upload evidence for this case first.")
    analysis = run_case_analysis(case_id, db, question=request.question.strip(),
        previous_questions=[turn.question.strip() for turn in request.history])
    if analysis.summary or analysis.documented_observations:
        status, message = "grounded", "Answer statements cite indexed evidence; verify their meaning against the sources."
    elif analysis.possible_interpretations:
        status, message = "interpretation_only", "Only tentative interpretations are available; the evidence does not establish a factual answer."
    else:
        status, message = "insufficient_evidence", "The indexed evidence does not support an answer to this question."
    return ChatResponse(**analysis.model_dump(), answer_status=status, message=message)


@router.get("/timeline", response_model=TimelineResponse)
def timeline(case_id: int, db: Session = Depends(get_db)):
    return build_timeline(case_id, db)


@router.post("/report")
def report(case_id: int, request: ReportRequest, db: Session = Depends(get_db)):
    return Response(build_report(case_id, request.analysis, db), media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="ChronicleAI-case-{case_id}.html"'})
