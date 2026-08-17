from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base, TimestampMixin


class Case(Base, TimestampMixin):
    """Case model representing an isolated container for investigation evidence and reconstruction."""
    __tablename__ = "cases"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")

    sources = relationship("Source", back_populates="case", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Case id={self.id} name='{self.name}' status='{self.status}'>"
