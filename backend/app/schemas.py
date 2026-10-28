from datetime import datetime
from typing import Optional, List, Literal, Any
from pydantic import BaseModel, ConfigDict, Field
from app.models import CaseStatus

# --- Case Schemas ---
class CaseBase(BaseModel):
    case_number: str = Field(..., min_length=1, max_length=100, description="Unique case number or identifier")
    title: str = Field(..., min_length=1, max_length=255, description="Case title")
    description: Optional[str] = Field(None, description="Optional detailed case description")
    status: CaseStatus = Field(default=CaseStatus.OPEN, description="Case status")

class CaseCreate(CaseBase):
    pass

class CaseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[CaseStatus] = None

class CaseResponse(CaseBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CaseStatsResponse(BaseModel):
    total_cases: int
    open_cases: int
    in_progress_cases: int
    closed_cases: int

# --- Evidence Schemas ---
class EvidenceFileResponse(BaseModel):
    id: int
    case_id: int
    original_filename: str
    stored_filename: str
    file_size: int
    sha256_hash: str
    encoding: str
    line_count: int
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)

class EvidenceLineResponse(BaseModel):
    id: int
    evidence_file_id: int
    line_number: int
    content: str

    model_config = ConfigDict(from_attributes=True)

class PaginatedLinesResponse(BaseModel):
    total_lines: int
    page: int
    page_size: int
    lines: List[EvidenceLineResponse]

class EvidenceVerifyResponse(BaseModel):
    evidence_id: int
    original_filename: str
    file_exists: bool
    hash_matched: bool
    stored_hash: str
    computed_hash: Optional[str] = None
    verification_status: str # "verified" | "corrupted" | "missing_file"
    message: str

# --- Search Schemas ---
class SearchResultItem(BaseModel):
    case_id: int
    evidence_file_id: int
    original_filename: str
    sha256_hash: str
    line_number: int
    line_content: str

    model_config = ConfigDict(from_attributes=True)

class SearchResponse(BaseModel):
    query: str
    case_id: int
    total_matches: int
    page: int
    page_size: int
    results: List[SearchResultItem]

# --- Entity Schemas ---
class EntityOccurrence(BaseModel):
    evidence_file_id: int
    original_filename: str
    text: str
    label: str # PERSON, ORG, GPE, LOC, DATE
    category: str # Person, Organization, Location, Date
    start_line: int
    end_line: int
    start_char: int
    end_char: int
    extraction_method: Optional[str] = "spacy_ner"

    model_config = ConfigDict(from_attributes=True)

class GroupedEntity(BaseModel):
    category: str
    display_text: str
    count: int
    occurrences: List[EntityOccurrence]

class CaseEntitiesResponse(BaseModel):
    case_id: int
    total_groups: int
    total_occurrences: int
    page: int
    page_size: int
    category_counts: dict[str, int]
    entities: List[GroupedEntity]

class CaseEntitiesSummaryResponse(BaseModel):
    case_id: int
    total_unique_entities: int
    total_occurrences: int
    category_counts: dict[str, int]
    evidence_files_processed: int

# --- AI Case Analysis Schemas (Phase 5) ---
class AnalysisCitation(BaseModel):
    evidence_file_id: int
    original_filename: str
    start_line: int
    end_line: int
    snippet: Optional[str] = None

class AnalysisClaim(BaseModel):
    statement: str
    classification: str = Field(..., description="'documented_observation' or 'possible_interpretation'")
    citations: List[AnalysisCitation] = Field(default_factory=list)

class AnalysisEvidenceScope(BaseModel):
    file_count: int
    line_count: int
    total_characters: int

class AnalysisResponse(BaseModel):
    case_id: int
    model_used: str
    evidence_scope: AnalysisEvidenceScope
    summary: List[AnalysisClaim] = Field(default_factory=list)
    documented_observations: List[AnalysisClaim] = Field(default_factory=list)
    possible_interpretations: List[AnalysisClaim] = Field(default_factory=list)
    unresolved_questions: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ChatHistoryTurn(BaseModel):
    case_id: int
    question: str = Field(..., min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    history: List[ChatHistoryTurn] = Field(default_factory=list, max_length=6)


class ChatResponse(AnalysisResponse):
    answer_status: Literal["grounded", "interpretation_only", "insufficient_evidence"]
    message: str


class TimelineEvent(BaseModel):
    date_text: str
    normalized_date: Optional[str] = None
    date_status: Literal["explicit", "ambiguous", "incomplete", "invalid"]
    description: str
    note: str
    citations: List[AnalysisCitation]


class TimelineResponse(BaseModel):
    case_id: int
    events: List[TimelineEvent]
    undated: List[TimelineEvent]
    disclaimer: str


class ReportRequest(BaseModel):
    # Keep raw coordinate types intact until the existing strict validator runs.
    analysis: Optional[dict[str, Any]] = None
