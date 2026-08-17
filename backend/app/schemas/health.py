from datetime import datetime
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="healthy", description="Overall health status")
    app_name: str = Field(description="Name of the application")
    version: str = Field(description="Application version")
    environment: str = Field(description="Deployment environment")
    database_connected: bool = Field(description="Database connectivity check result")
    timestamp: datetime = Field(description="Current server time (UTC)")
