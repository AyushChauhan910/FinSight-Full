from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class IngestRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10, description="Stock ticker symbol")
    years: int = Field(default=3, ge=1, le=10, description="Number of years of filings to ingest")


class IngestResponse(BaseModel):
    job_id: str
    status: JobStatus


class IngestionResultResponse(BaseModel):
    ticker: str
    filings_processed: int
    chunks_created: int
    tokens_embedded: int
    duration_seconds: float


class IngestStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: Optional[str] = None
    result: Optional[IngestionResultResponse] = None
    error: Optional[str] = None


class ResearchQueryRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)
    query: str = Field(..., min_length=1, max_length=2000)


class ResearchReportRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)


class CitationItem(BaseModel):
    chunk_id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentResultResponse(BaseModel):
    answer: str
    report: dict[str, Any]
    citations: list[CitationItem]
    iterations_used: int
    tokens_used: int


class CompanyStatsResponse(BaseModel):
    ticker: str
    document_count: int
    total_tokens: int
    filing_dates: list[str]
    form_types: list[str]
    sections: list[str]


class CompanyListResponse(BaseModel):
    companies: list[CompanyStatsResponse]


class StreamEvent(BaseModel):
    event: str
    data: str
