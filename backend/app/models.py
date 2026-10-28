from datetime import datetime, timezone
import enum
from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base

class CaseStatus(str, enum.Enum):
    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    CLOSED = "Closed"

class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    case_number = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(CaseStatus), nullable=False, default=CaseStatus.OPEN)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    evidence_files = relationship("EvidenceFile", back_populates="case", cascade="all, delete-orphan")

class EvidenceFile(Base):
    __tablename__ = "evidence_files"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), unique=True, nullable=False)
    file_size = Column(Integer, nullable=False)
    sha256_hash = Column(String(64), nullable=False, index=True)
    encoding = Column(String(50), nullable=False, default="utf-8")
    line_count = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    case = relationship("Case", back_populates="evidence_files")
    lines = relationship("EvidenceLine", back_populates="evidence_file", cascade="all, delete-orphan", order_by="EvidenceLine.line_number")

    __table_args__ = (
        UniqueConstraint("case_id", "sha256_hash", name="uq_case_sha256"),
    )

class EvidenceLine(Base):
    __tablename__ = "evidence_lines"

    id = Column(Integer, primary_key=True, index=True)
    evidence_file_id = Column(Integer, ForeignKey("evidence_files.id", ondelete="CASCADE"), nullable=False, index=True)
    line_number = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)

    evidence_file = relationship("EvidenceFile", back_populates="lines")

    __table_args__ = (
        UniqueConstraint("evidence_file_id", "line_number", name="uq_file_line_number"),
    )
