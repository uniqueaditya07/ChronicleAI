import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.models import Case, EvidenceFile, EvidenceLine
from app.schemas import (
    EvidenceFileResponse,
    EvidenceLineResponse,
    PaginatedLinesResponse,
    EvidenceVerifyResponse
)
from app.storage import (
    compute_sha256,
    validate_and_decode_txt,
    save_original_file,
    remove_stored_file,
    get_case_storage_dir
)

router = APIRouter(prefix="/api/cases/{case_id}/evidence", tags=["evidence"])

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

def get_verified_case(case_id: int, db: Session) -> Case:
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with ID {case_id} not found."
        )
    return case

@router.post("", response_model=EvidenceFileResponse, status_code=status.HTTP_201_CREATED)
async def upload_evidence_file(
    case_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # 1. Verify case exists
    get_verified_case(case_id, db)

    # 2. Validate filename and extension
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Filename must not be empty."
        )

    clean_filename = os.path.basename(file.filename)
    if not clean_filename.lower().endswith(".txt"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type: only plain text (.txt) evidence files are accepted."
        )

    # 3. Read content in bounded chunks to prevent unbounded memory usage
    chunk_size = 64 * 1024  # 64 KB
    data = bytearray()
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size of 5 MB ({len(data)} bytes)."
            )

    file_bytes = bytes(data)

    # 4. Check for nonempty content
    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Evidence file is empty."
        )

    # 5. Calculate SHA-256 hash of original bytes
    sha256_hash = compute_sha256(file_bytes)

    # 6. Check for duplicate content within the same case
    existing_evidence = db.query(EvidenceFile).filter(
        EvidenceFile.case_id == case_id,
        EvidenceFile.sha256_hash == sha256_hash
    ).first()
    if existing_evidence:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate evidence detected: file with identical SHA-256 hash ({sha256_hash[:16]}...) already exists in case {case_id} as '{existing_evidence.original_filename}'."
        )

    # 7. Validate text encoding & decode logical lines
    try:
        encoding, _, lines = validate_and_decode_txt(file_bytes)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(e)
        )

    # 8. Save original bytes to disk atomically
    stored_filename = None
    try:
        stored_filename, _ = save_original_file(case_id, clean_filename, file_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store evidence file: {str(e)}"
        )

    # 9. Store metadata and line index in database within a transaction
    try:
        evidence_file = EvidenceFile(
            case_id=case_id,
            original_filename=clean_filename,
            stored_filename=stored_filename,
            file_size=len(file_bytes),
            sha256_hash=sha256_hash,
            encoding=encoding,
            line_count=len(lines)
        )
        db.add(evidence_file)
        db.flush()  # Flush to get evidence_file.id

        # Insert lines in bulk or sequential rows
        evidence_lines = [
            EvidenceLine(
                evidence_file_id=evidence_file.id,
                line_number=idx + 1,
                content=line_text
            )
            for idx, line_text in enumerate(lines)
        ]
        db.add_all(evidence_lines)
        db.commit()
        db.refresh(evidence_file)
        return evidence_file
    except IntegrityError:
        db.rollback()
        if stored_filename:
            remove_stored_file(case_id, stored_filename)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate evidence conflict occurred during ingestion."
        )
    except Exception as e:
        db.rollback()
        if stored_filename:
            remove_stored_file(case_id, stored_filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete evidence indexing: {str(e)}"
        )

@router.get("", response_model=List[EvidenceFileResponse])
def list_case_evidence(case_id: int, db: Session = Depends(get_db)):
    get_verified_case(case_id, db)
    evidence_files = db.query(EvidenceFile).filter(
        EvidenceFile.case_id == case_id
    ).order_by(EvidenceFile.uploaded_at.desc()).all()
    return evidence_files

@router.get("/{evidence_id}", response_model=EvidenceFileResponse)
def get_evidence_metadata(case_id: int, evidence_id: int, db: Session = Depends(get_db)):
    get_verified_case(case_id, db)
    evidence = db.query(EvidenceFile).filter(
        EvidenceFile.id == evidence_id,
        EvidenceFile.case_id == case_id
    ).first()
    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence with ID {evidence_id} not found in case {case_id}."
        )
    return evidence

@router.get("/{evidence_id}/lines", response_model=PaginatedLinesResponse)
def get_evidence_lines(
    case_id: int,
    evidence_id: int,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(500, ge=1, le=2000, description="Lines per page"),
    db: Session = Depends(get_db)
):
    get_verified_case(case_id, db)
    evidence = db.query(EvidenceFile).filter(
        EvidenceFile.id == evidence_id,
        EvidenceFile.case_id == case_id
    ).first()
    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence with ID {evidence_id} not found in case {case_id}."
        )

    total_lines = db.query(EvidenceLine).filter(
        EvidenceLine.evidence_file_id == evidence_id
    ).count()

    offset = (page - 1) * page_size
    lines = db.query(EvidenceLine).filter(
        EvidenceLine.evidence_file_id == evidence_id
    ).order_by(EvidenceLine.line_number.asc()).offset(offset).limit(page_size).all()

    return PaginatedLinesResponse(
        total_lines=total_lines,
        page=page,
        page_size=page_size,
        lines=lines
    )

@router.get("/{evidence_id}/verify", response_model=EvidenceVerifyResponse)
def verify_evidence_integrity(case_id: int, evidence_id: int, db: Session = Depends(get_db)):
    get_verified_case(case_id, db)
    evidence = db.query(EvidenceFile).filter(
        EvidenceFile.id == evidence_id,
        EvidenceFile.case_id == case_id
    ).first()
    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence with ID {evidence_id} not found in case {case_id}."
        )

    case_dir = get_case_storage_dir(case_id)
    file_path = os.path.join(case_dir, evidence.stored_filename)

    if not os.path.exists(file_path):
        return EvidenceVerifyResponse(
            evidence_id=evidence.id,
            original_filename=evidence.original_filename,
            file_exists=False,
            hash_matched=False,
            stored_hash=evidence.sha256_hash,
            computed_hash=None,
            verification_status="missing_file",
            message="Evidence file missing on filesystem: integrity verification failed."
        )

    with open(file_path, "rb") as f:
        stored_bytes = f.read()

    computed_hash = compute_sha256(stored_bytes)
    matched = (computed_hash.lower() == evidence.sha256_hash.lower())

    if matched:
        return EvidenceVerifyResponse(
            evidence_id=evidence.id,
            original_filename=evidence.original_filename,
            file_exists=True,
            hash_matched=True,
            stored_hash=evidence.sha256_hash,
            computed_hash=computed_hash,
            verification_status="verified",
            message="Evidence integrity verified: byte-for-byte hash matches recorded record."
        )
    else:
        return EvidenceVerifyResponse(
            evidence_id=evidence.id,
            original_filename=evidence.original_filename,
            file_exists=True,
            hash_matched=False,
            stored_hash=evidence.sha256_hash,
            computed_hash=computed_hash,
            verification_status="corrupted",
            message="CRITICAL: Evidence hash mismatch! Stored bytes have been modified or corrupted."
        )
