"""
Database models for the Thesis Formatter application.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def generate_uuid() -> uuid.UUID:
    """Generate a new UUID."""
    return uuid.uuid4()


class Task(Base):
    """
    Task model representing a format check task.
    """

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    thesis_file_key: Mapped[str] = mapped_column(String(255), nullable=False)
    spec_file_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    template_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("templates.id", ondelete="SET NULL"), nullable=True
    )
    model_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    rule_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    result_summary: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    fixed_file_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    issues: Mapped[list["Issue"]] = relationship(
        "Issue", back_populates="task", cascade="all, delete-orphan"
    )
    changes: Mapped[list["Change"]] = relationship(
        "Change", back_populates="task", cascade="all, delete-orphan"
    )
    template: Mapped[Optional["Template"]] = relationship("Template", back_populates="tasks")


class Issue(Base):
    """
    Issue model representing a format issue found in a document.
    """

    __tablename__ = "issues"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    severity: Mapped[str] = mapped_column(String(10), nullable=False)  # error, warning, info
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # margin, font, spacing, etc.
    location: Mapped[dict] = mapped_column(JSONB, nullable=False)  # {page, paragraph, section}
    rule_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    current_value: Mapped[str] = mapped_column(Text, nullable=False)
    expected_value: Mapped[str] = mapped_column(Text, nullable=False)
    suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_fixed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="issues")
    changes: Mapped[list["Change"]] = relationship(
        "Change", back_populates="issue", cascade="all, delete-orphan"
    )


class Change(Base):
    """
    Change model representing a format modification made to a document.
    """

    __tablename__ = "changes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    issue_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.id", ondelete="SET NULL"), nullable=True
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    location: Mapped[dict] = mapped_column(JSONB, nullable=False)
    before_value: Mapped[str] = mapped_column(Text, nullable=False)
    after_value: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False)  # low, medium, high
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="changes")
    issue: Mapped[Optional["Issue"]] = relationship("Issue", back_populates="changes")


class Rule(Base):
    """
    Rule model representing a set of format rules.
    """

    __tablename__ = "rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # ai_parsed, manual, template
    rule_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    school_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Relationships
    templates: Mapped[list["Template"]] = relationship("Template", back_populates="rule")


class Template(Base):
    """
    Template model representing a pre-configured school template.
    """

    __tablename__ = "templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    school_name: Mapped[str] = mapped_column(String(100), nullable=False)
    thesis_type: Mapped[str] = mapped_column(String(20), nullable=False)  # bachelor, master, doctor
    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rules.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Relationships
    rule: Mapped["Rule"] = relationship("Rule", back_populates="templates")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="template")


class ModelConfig(Base):
    """
    ModelConfig model representing an AI model configuration.
    """

    __tablename__ = "model_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # openai, deepseek, qwen, ollama
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
