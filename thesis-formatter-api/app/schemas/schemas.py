"""
Pydantic schemas for API request/response models.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ─── Common ───
class ResponseBase(BaseModel):
    """Base response model."""

    class Config:
        from_attributes = True


# ─── Task Schemas ───
class TaskCreate(BaseModel):
    """Request model for creating a task (handled via multipart form)."""

    template_id: Optional[UUID] = None
    model_id: Optional[str] = None


class TaskStatus(BaseModel):
    """Task status response."""

    id: UUID
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    issue_count: Optional[int] = None
    fix_available: Optional[bool] = None
    error_message: Optional[str] = None


class IssueLocation(BaseModel):
    """Location of an issue in a document."""

    page: Optional[int] = None
    paragraph: Optional[int] = None
    section: Optional[int] = None


class IssueResponse(BaseModel):
    """Response model for a single issue."""

    id: UUID
    severity: str  # error, warning, info
    category: str  # margin, font, spacing, heading, page_num, ref
    location: IssueLocation
    rule_id: Optional[str] = None
    current_value: str
    expected_value: str
    suggestion: Optional[str] = None
    is_fixed: bool = False

    class Config:
        from_attributes = True


class ReportSummary(BaseModel):
    """Summary of format check report."""

    total_issues: int
    error_count: int
    warning_count: int
    info_count: int
    categories: dict[str, int]  # {margin: 2, font: 5, ...}
    score: Optional[float] = None  # Overall format score (0-100)


class TaskReport(BaseModel):
    """Full format check report for a task."""

    task_id: UUID
    summary: ReportSummary
    issues: list[IssueResponse]
    rules_applied: list[dict[str, Any]]
    metadata: dict[str, Any]  # {page_count, word_count, title, school}


class ChangeRecord(BaseModel):
    """A single change record."""

    id: UUID
    category: str
    location: IssueLocation
    before_value: str
    after_value: str
    risk_level: str  # low, medium, high
    created_at: datetime

    class Config:
        from_attributes = True


class ChangeLogResponse(BaseModel):
    """Response model for change log."""

    task_id: UUID
    total_changes: int
    changes: list[ChangeRecord]


# ─── Rule Schemas ───
class RuleData(BaseModel):
    """Structured format rule data."""

    school_name: Optional[str] = None
    thesis_type: Optional[str] = None  # bachelor, master, doctor

    # Page settings
    page_margin: Optional[dict[str, str]] = None  # {top: "2.5cm", bottom: "2.5cm", ...}

    # Font settings
    font: Optional[dict[str, str]] = None  # {cn_body: "宋体", en_body: "Times New Roman", ...}
    font_size: Optional[dict[str, str]] = None  # {body: "12pt", heading1: "22pt", ...}

    # Spacing settings
    line_spacing: Optional[dict[str, str]] = None  # {body: "1.5倍", block_quote: "单倍"}
    paragraph_spacing: Optional[dict[str, dict[str, str]]] = None  # {body: {before: "0pt", after: "0pt"}}

    # Heading styles
    heading_style: Optional[dict[str, dict[str, Any]]] = None  # {heading1: {font: "黑体", size: "22pt", ...}}

    # Page number
    page_number: Optional[dict[str, Any]] = None  # {position: "footer-center", format: "arabic", ...}

    # References
    references: Optional[dict[str, Any]] = None  # {indent: "悬挂缩进", indent_width: "2字符"}


class RuleCreate(BaseModel):
    """Request model for creating a rule."""

    name: str
    source: str = "manual"  # ai_parsed, manual, template
    rule_data: RuleData
    school_name: Optional[str] = None


class RuleResponse(BaseModel):
    """Response model for a rule."""

    id: UUID
    name: str
    source: str
    rule_data: dict[str, Any]
    school_name: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Template Schemas ───
class TemplateResponse(BaseModel):
    """Response model for a template."""

    id: UUID
    school_name: str
    thesis_type: str
    description: Optional[str]
    usage_count: int
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Model Config Schemas ───
class ModelConfigCreate(BaseModel):
    """Request model for creating/updating a model config."""

    name: str = Field(..., description="Display name, e.g., 'DeepSeek-V3'")
    api_key: str = Field(..., description="API key (will be encrypted)")
    base_url: str = Field(..., description="API base URL")
    model_name: str = Field(..., description="Model identifier, e.g., 'deepseek-chat'")
    is_default: bool = False


class ModelConfigResponse(BaseModel):
    """Response model for a model config (without API key)."""

    id: UUID
    name: str
    provider: str
    base_url: str
    model_name: str
    is_default: bool
    priority: int
    created_at: datetime

    class Config:
        from_attributes = True


# ─── File Upload Schemas ───
class UploadResponse(BaseModel):
    """Response after successful file upload."""

    file_key: str
    file_name: str
    file_size: int
    content_type: str


# ─── Error Schemas ───
class ErrorResponse(BaseModel):
    """Error response model."""

    detail: str
    error_code: Optional[str] = None
