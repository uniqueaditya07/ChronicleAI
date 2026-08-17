from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class CaseBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Name of the case")
    description: str | None = Field(None, description="Detailed case description")


class CaseCreate(CaseBase):
    pass


class CaseUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = Field(None, pattern="^(active|archived|deleted)$")


class CaseResponse(CaseBase):
    id: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CaseListResponse(BaseModel):
    items: list[CaseResponse]
    total: int
