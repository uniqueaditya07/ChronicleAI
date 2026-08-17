import enum
from sqlalchemy import String, Text, Integer, ForeignKey, Enum as SQLEnum, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base, TimestampMixin

class ProcessingStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"

class ChunkType(str, enum.Enum):
    page = "page"
    paragraph = "paragraph"
    row = "row"
    image_region = "image_region"
    log_entry = "log_entry"

class Source(Base, TimestampMixin):
    """Source model representing an uploaded document or file."""
    __tablename__ = "sources"

    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    processing_status: Mapped[str] = mapped_column(
        SQLEnum(ProcessingStatus, native_enum=False), 
        nullable=False, 
        default=ProcessingStatus.pending.value
    )
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship to parent Case (assumes Case model defines a back_populates="sources")
    case = relationship("Case", back_populates="sources")
    
    # Relationship to SourceChunks
    chunks = relationship("SourceChunk", back_populates="source", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("case_id", "content_hash", name="uq_source_case_hash"),
    )

    def __repr__(self) -> str:
        return f"<Source id={self.id} case_id={self.case_id} original_filename='{self.original_filename}' status='{self.processing_status}'>"

class SourceChunk(Base, TimestampMixin):
    """Atomic unit of text extraction from a source."""
    __tablename__ = "source_chunks"

    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    chunk_type: Mapped[str] = mapped_column(SQLEnum(ChunkType, native_enum=False), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    source = relationship("Source", back_populates="chunks")

    __table_args__ = (
        Index("ix_source_chunk_index", "source_id", "chunk_index"),
    )

    def __repr__(self) -> str:
        return f"<SourceChunk id={self.id} source_id={self.source_id} index={self.chunk_index} type='{self.chunk_type}'>"
