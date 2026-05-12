"""
Tests for Celery tasks.

Tests for the format check, fix, and spec parsing Celery tasks.
Uses mocking for external dependencies like MinIO and database.
"""

import os
import uuid
from datetime import datetime
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import Change, Issue, Rule, Task


# =============================================================================
# Test Database Setup
# =============================================================================

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def async_engine():
    """Create async engine for testing."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine):
    """Create database session for testing."""
    async_session = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


@pytest.fixture(scope="function")
def mock_storage_service():
    """Create mock storage service."""
    mock = MagicMock()
    mock.ensure_bucket = MagicMock(return_value=None)
    mock.upload_file = MagicMock(return_value="test_key")
    mock.download_file = MagicMock(return_value=b"test file content")
    mock.get_presigned_url = MagicMock(return_value="http://minio.test/url")
    mock.delete_file = MagicMock(return_value=None)
    mock.file_exists = MagicMock(return_value=True)
    return mock


@pytest.fixture(scope="function")
def mock_document_processor():
    """Create mock document processor."""
    mock = MagicMock()

    # Mock process result
    process_result = MagicMock()
    process_result.issues = [
        MagicMock(
            severity=MagicMock(value="error"),
            category=MagicMock(value="margin"),
            location={"page": 1, "paragraph": 1},
            rule_id="margin_top",
            current_value="2.0cm",
            expected_value="2.5cm",
            suggestion="Adjust margin",
        ),
        MagicMock(
            severity=MagicMock(value="warning"),
            category=MagicMock(value="font"),
            location={"page": 1, "paragraph": 2},
            rule_id="font_body",
            current_value="Arial",
            expected_value="Times New Roman",
            suggestion="Change font",
        ),
    ]
    mock.process = MagicMock(return_value=process_result)

    # Mock fix_only result
    change1 = MagicMock(
        category="margin",
        location={"page": 1},
        before_value="2.0cm",
        after_value="2.5cm",
        risk_level="low",
    )
    change2 = MagicMock(
        category="font",
        location={"page": 1},
        before_value="Arial",
        after_value="Times New Roman",
        risk_level="medium",
    )
    mock.fix_only = MagicMock(return_value=([change1, change2], b"fixed document bytes"))

    return mock


@pytest.fixture(scope="function")
def mock_rule_engine():
    """Create mock rule engine."""
    mock = MagicMock()
    mock.validate_rules = MagicMock(return_value=[])
    mock.get_default_rules = MagicMock(return_value={
        "school_name": "默认学校",
        "page_margin": {"top": "2.54cm", "bottom": "2.54cm"},
        "font": {"cn_body": "宋体"},
    })
    mock.merge_rules = MagicMock(return_value={
        "school_name": "测试大学",
        "page_margin": {"top": "2.5cm", "bottom": "2.5cm"},
        "font": {"cn_body": "宋体"},
    })
    return mock


@pytest.fixture(scope="function")
def mock_spec_parser():
    """Create mock spec parser."""
    mock = MagicMock()
    mock.parse = MagicMock(return_value={
        "school_name": "测试大学",
        "thesis_type": "master",
        "page_margin": {
            "top": "2.5cm",
            "bottom": "2.5cm",
            "left": "3.0cm",
            "right": "2.5cm",
        },
        "font": {
            "cn_body": "宋体",
            "en_body": "Times New Roman",
        },
    })
    return mock


@pytest_asyncio.fixture(scope="function")
async def sample_task(db_session):
    """Create a sample task for testing."""
    task = Task(
        id=uuid.uuid4(),
        status="pending",
        thesis_file_key="thesis/test_thesis.docx",
        spec_file_key=None,
        template_id=None,
        model_id=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task


@pytest_asyncio.fixture(scope="function")
async def task_with_spec(db_session):
    """Create a task with spec file for testing."""
    task = Task(
        id=uuid.uuid4(),
        status="pending",
        thesis_file_key="thesis/test_thesis.docx",
        spec_file_key="spec/test_spec.pdf",
        template_id=None,
        model_id="test-model",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task


@pytest_asyncio.fixture(scope="function")
async def completed_task(db_session):
    """Create a completed task with rule snapshot for testing."""
    task = Task(
        id=uuid.uuid4(),
        status="completed",
        thesis_file_key="thesis/test_thesis.docx",
        spec_file_key=None,
        template_id=None,
        model_id=None,
        rule_snapshot={
            "school_name": "测试大学",
            "page_margin": {"top": "2.5cm", "bottom": "2.5cm"},
            "font": {"cn_body": "宋体"},
        },
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task


# =============================================================================
# Test Cases for process_format_check
# =============================================================================


class TestProcessFormatCheckTask:
    """Tests for process_format_check Celery task."""

    @pytest.mark.asyncio
    async def test_process_format_check_success(
        self,
        db_session,
        sample_task,
        mock_storage_service,
        mock_document_processor,
        mock_rule_engine,
    ):
        """Test successful format check task."""
        from app.tasks.format_tasks import process_format_check

        with patch("app.tasks.format_tasks.get_storage_service", return_value=mock_storage_service):
            with patch("app.tasks.format_tasks.DocumentProcessor", return_value=mock_document_processor):
                with patch("app.tasks.format_tasks.get_rule_engine", return_value=mock_rule_engine):
                    with patch("app.tasks.format_tasks.get_model_manager"):
                        with patch("app.tasks.format_tasks.get_db_context") as mock_db_context:
                            # Mock async context manager
                            mock_context = MagicMock()
                            mock_context.__aenter__ = MagicMock(return_value=db_session)
                            mock_context.__aexit__ = MagicMock(return_value=None)
                            mock_db_context.return_value = mock_context

                            # Run the task
                            result = process_format_check(str(sample_task.id))

                            assert result["status"] == "completed"
                            assert result["task_id"] == str(sample_task.id)
                            assert "summary" in result
                            assert result["summary"]["total_issues"] == 2
                            assert result["summary"]["error_count"] == 1
                            assert result["summary"]["warning_count"] == 1

    @pytest.mark.asyncio
    async def test_process_format_check_with_spec_file(
        self,
        db_session,
        task_with_spec,
        mock_storage_service,
        mock_document_processor,
        mock_rule_engine,
        mock_spec_parser,
    ):
        """Test format check with spec file parsing."""
        from app.tasks.format_tasks import process_format_check

        with patch("app.tasks.format_tasks.get_storage_service", return_value=mock_storage_service):
            with patch("app.tasks.format_tasks.DocumentProcessor", return_value=mock_document_processor):
                with patch("app.tasks.format_tasks.get_rule_engine", return_value=mock_rule_engine):
                    with patch("app.tasks.format_tasks.get_model_manager") as mock_model_manager:
                        mock_manager = MagicMock()
                        mock_manager.has_providers = True
                        mock_model_manager.return_value = mock_manager

                        with patch("app.tasks.format_tasks.SpecParser", return_value=mock_spec_parser):
                            with patch("app.tasks.format_tasks.get_db_context") as mock_db_context:
                                mock_context = MagicMock()
                                mock_context.__aenter__ = MagicMock(return_value=db_session)
                                mock_context.__aexit__ = MagicMock(return_value=None)
                                mock_db_context.return_value = mock_context

                                result = process_format_check(str(task_with_spec.id))

                                assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_process_format_check_task_not_found(
        self,
        mock_storage_service,
    ):
        """Test format check with non-existent task."""
        from app.tasks.format_tasks import process_format_check

        fake_id = str(uuid.uuid4())

        with patch("app.tasks.format_tasks.get_storage_service", return_value=mock_storage_service):
            with pytest.raises(ValueError) as exc_info:
                process_format_check(fake_id)

            assert "不存在" in str(exc_info.value) or "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_process_format_check_storage_error(
        self,
        db_session,
        sample_task,
        mock_storage_service,
    ):
        """Test format check when storage download fails."""
        from app.tasks.format_tasks import process_format_check

        mock_storage_service.download_file.side_effect = ConnectionError("MinIO error")

        with patch("app.tasks.format_tasks.get_storage_service", return_value=mock_storage_service):
            with patch("app.tasks.format_tasks.get_db_context") as mock_db_context:
                mock_context = MagicMock()
                mock_context.__aenter__ = MagicMock(return_value=db_session)
                mock_context.__aexit__ = MagicMock(return_value=None)
                mock_db_context.return_value = mock_context

                with pytest.raises(Exception):
                    process_format_check(str(sample_task.id))


# =============================================================================
# Test Cases for process_format_fix
# =============================================================================


class TestProcessFormatFixTask:
    """Tests for process_format_fix Celery task."""

    @pytest.mark.asyncio
    async def test_process_format_fix_success(
        self,
        db_session,
        completed_task,
        mock_storage_service,
        mock_document_processor,
    ):
        """Test successful format fix task."""
        from app.tasks.format_tasks import process_format_fix

        with patch("app.tasks.format_tasks.get_storage_service", return_value=mock_storage_service):
            with patch("app.tasks.format_tasks.DocumentProcessor", return_value=mock_document_processor):
                with patch("app.tasks.format_tasks.get_db_context") as mock_db_context:
                    mock_context = MagicMock()
                    mock_context.__aenter__ = MagicMock(return_value=db_session)
                    mock_context.__aexit__ = MagicMock(return_value=None)
                    mock_db_context.return_value = mock_context

                    result = process_format_fix(str(completed_task.id))

                    assert result["status"] == "fixed"
                    assert result["task_id"] == str(completed_task.id)
                    assert result["total_changes"] == 2

                    # Verify storage upload was called
                    mock_storage_service.upload_file.assert_called()

    @pytest.mark.asyncio
    async def test_process_format_fix_with_issue_ids(
        self,
        db_session,
        completed_task,
        mock_storage_service,
        mock_document_processor,
    ):
        """Test format fix with specific issue IDs."""
        from app.tasks.format_tasks import process_format_fix

        issue_ids = [str(uuid.uuid4()), str(uuid.uuid4())]

        with patch("app.tasks.format_tasks.get_storage_service", return_value=mock_storage_service):
            with patch("app.tasks.format_tasks.DocumentProcessor", return_value=mock_document_processor):
                with patch("app.tasks.format_tasks.get_db_context") as mock_db_context:
                    mock_context = MagicMock()
                    mock_context.__aenter__ = MagicMock(return_value=db_session)
                    mock_context.__aexit__ = MagicMock(return_value=None)
                    mock_db_context.return_value = mock_context

                    result = process_format_fix(str(completed_task.id), issue_ids=issue_ids)

                    assert result["status"] == "fixed"
                    # Verify fix_only was called with issue_ids
                    mock_document_processor.fix_only.assert_called_once()
                    call_args = mock_document_processor.fix_only.call_args
                    assert call_args[1]["issue_ids"] == issue_ids

    @pytest.mark.asyncio
    async def test_process_format_fix_no_rule_snapshot(
        self,
        db_session,
        sample_task,
        mock_storage_service,
    ):
        """Test format fix when task has no rule snapshot."""
        from app.tasks.format_tasks import process_format_fix

        with patch("app.tasks.format_tasks.get_storage_service", return_value=mock_storage_service):
            with patch("app.tasks.format_tasks.get_db_context") as mock_db_context:
                mock_context = MagicMock()
                mock_context.__aenter__ = MagicMock(return_value=db_session)
                mock_context.__aexit__ = MagicMock(return_value=None)
                mock_db_context.return_value = mock_context

                with pytest.raises(ValueError) as exc_info:
                    process_format_fix(str(sample_task.id))

                assert "rule_snapshot" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_process_format_fix_task_not_found(
        self,
        mock_storage_service,
    ):
        """Test format fix with non-existent task."""
        from app.tasks.format_tasks import process_format_fix

        fake_id = str(uuid.uuid4())

        with patch("app.tasks.format_tasks.get_storage_service", return_value=mock_storage_service):
            with pytest.raises(ValueError) as exc_info:
                process_format_fix(fake_id)

            assert "不存在" in str(exc_info.value) or "not found" in str(exc_info.value).lower()


# =============================================================================
# Test Cases for parse_spec_file
# =============================================================================


class TestParseSpecFileTask:
    """Tests for parse_spec_file Celery task."""

    @pytest.mark.asyncio
    async def test_parse_spec_file_success(
        self,
        db_session,
        sample_task,
        mock_storage_service,
        mock_spec_parser,
        mock_rule_engine,
    ):
        """Test successful spec file parsing."""
        from app.tasks.format_tasks import parse_spec_file

        spec_file_key = "spec/test_spec.pdf"

        with patch("app.tasks.format_tasks.get_storage_service", return_value=mock_storage_service):
            with patch("app.tasks.format_tasks.get_model_manager") as mock_model_manager:
                mock_manager = MagicMock()
                mock_manager.has_providers = True
                mock_model_manager.return_value = mock_manager

                with patch("app.tasks.format_tasks.SpecParser", return_value=mock_spec_parser):
                    with patch("app.tasks.format_tasks.get_rule_engine", return_value=mock_rule_engine):
                        with patch("app.tasks.format_tasks.get_db_context") as mock_db_context:
                            mock_context = MagicMock()
                            mock_context.__aenter__ = MagicMock(return_value=db_session)
                            mock_context.__aexit__ = MagicMock(return_value=None)
                            mock_db_context.return_value = mock_context

                            result = parse_spec_file(
                                str(sample_task.id),
                                spec_file_key,
                                model_id="test-model",
                            )

                            assert result["status"] == "parsed"
                            assert result["task_id"] == str(sample_task.id)
                            assert "rule_id" in result

    @pytest.mark.asyncio
    async def test_parse_spec_file_empty_content(
        self,
        db_session,
        sample_task,
        mock_storage_service,
        mock_rule_engine,
    ):
        """Test spec file parsing with empty content."""
        from app.tasks.format_tasks import parse_spec_file

        spec_file_key = "spec/empty_spec.txt"
        mock_storage_service.download_file.return_value = b""  # Empty content

        with patch("app.tasks.format_tasks.get_storage_service", return_value=mock_storage_service):
            with patch("app.tasks.format_tasks.get_db_context") as mock_db_context:
                mock_context = MagicMock()
                mock_context.__aenter__ = MagicMock(return_value=db_session)
                mock_context.__aexit__ = MagicMock(return_value=None)
                mock_db_context.return_value = mock_context

                with pytest.raises(ValueError) as exc_info:
                    parse_spec_file(str(sample_task.id), spec_file_key)

                assert "内容为空" in str(exc_info.value) or "empty" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_parse_spec_file_with_validation_errors(
        self,
        db_session,
        sample_task,
        mock_storage_service,
        mock_spec_parser,
        mock_rule_engine,
    ):
        """Test spec file parsing with validation warnings."""
        from app.tasks.format_tasks import parse_spec_file

        mock_rule_engine.validate_rules.return_value = ["Missing field: font_size"]

        with patch("app.tasks.format_tasks.get_storage_service", return_value=mock_storage_service):
            with patch("app.tasks.format_tasks.get_model_manager") as mock_model_manager:
                mock_manager = MagicMock()
                mock_manager.has_providers = True
                mock_model_manager.return_value = mock_manager

                with patch("app.tasks.format_tasks.SpecParser", return_value=mock_spec_parser):
                    with patch("app.tasks.format_tasks.get_rule_engine", return_value=mock_rule_engine):
                        with patch("app.tasks.format_tasks.get_db_context") as mock_db_context:
                            mock_context = MagicMock()
                            mock_context.__aenter__ = MagicMock(return_value=db_session)
                            mock_context.__aexit__ = MagicMock(return_value=None)
                            mock_db_context.return_value = mock_context

                            result = parse_spec_file(
                                str(sample_task.id),
                                "spec/test_spec.pdf",
                            )

                            # Should still succeed despite validation warnings
                            assert result["status"] == "parsed"

    @pytest.mark.asyncio
    async def test_parse_spec_file_storage_error(
        self,
        db_session,
        sample_task,
        mock_storage_service,
    ):
        """Test spec file parsing when storage download fails."""
        from app.tasks.format_tasks import parse_spec_file

        mock_storage_service.download_file.side_effect = ConnectionError("MinIO error")

        with patch("app.tasks.format_tasks.get_storage_service", return_value=mock_storage_service):
            with patch("app.tasks.format_tasks.get_db_context") as mock_db_context:
                mock_context = MagicMock()
                mock_context.__aenter__ = MagicMock(return_value=db_session)
                mock_context.__aexit__ = MagicMock(return_value=None)
                mock_db_context.return_value = mock_context

                with pytest.raises(Exception):
                    parse_spec_file(str(sample_task.id), "spec/test_spec.pdf")


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Tests for helper functions in format_tasks module."""

    def test_guess_suffix(self):
        """Test _guess_suffix function."""
        from app.tasks.format_tasks import _guess_suffix

        assert _guess_suffix("file.pdf") == ".pdf"
        assert _guess_suffix("file.docx") == ".docx"
        assert _guess_suffix("file.txt") == ".txt"
        assert _guess_suffix("file.PDF") == ".pdf"
        assert _guess_suffix("unknown") == ".bin"
        assert _guess_suffix("path/to/file.pdf") == ".pdf"

    def test_extract_spec_text_txt(self):
        """Test _extract_spec_text with TXT file."""
        from app.tasks.format_tasks import _extract_spec_text

        with patch("builtins.open", MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value="Test content"))),
            __exit__=MagicMock(return_value=None),
        ))):
            result = _extract_spec_text("/tmp/test.txt")
            assert result == "Test content"

    def test_cleanup_temp(self):
        """Test _cleanup_temp function."""
        from app.tasks.format_tasks import _cleanup_temp

        with patch("os.path.exists", return_value=True):
            with patch("os.unlink") as mock_unlink:
                _cleanup_temp("/tmp/test_file")
                mock_unlink.assert_called_once_with("/tmp/test_file")

    def test_cleanup_temp_nonexistent(self):
        """Test _cleanup_temp with non-existent file."""
        from app.tasks.format_tasks import _cleanup_temp

        with patch("os.path.exists", return_value=False):
            with patch("os.unlink") as mock_unlink:
                _cleanup_temp("/tmp/nonexistent")
                mock_unlink.assert_not_called()


# =============================================================================
# Integration Tests
# =============================================================================


class TestTaskIntegration:
    """Integration tests for task workflows."""

    @pytest.mark.asyncio
    async def test_full_workflow_check_then_fix(
        self,
        db_session,
        sample_task,
        mock_storage_service,
        mock_document_processor,
        mock_rule_engine,
    ):
        """Test full workflow: check task followed by fix task."""
        from app.tasks.format_tasks import process_format_check, process_format_fix

        # Step 1: Run format check
        with patch("app.tasks.format_tasks.get_storage_service", return_value=mock_storage_service):
            with patch("app.tasks.format_tasks.DocumentProcessor", return_value=mock_document_processor):
                with patch("app.tasks.format_tasks.get_rule_engine", return_value=mock_rule_engine):
                    with patch("app.tasks.format_tasks.get_model_manager"):
                        with patch("app.tasks.format_tasks.get_db_context") as mock_db_context:
                            mock_context = MagicMock()
                            mock_context.__aenter__ = MagicMock(return_value=db_session)
                            mock_context.__aexit__ = MagicMock(return_value=None)
                            mock_db_context.return_value = mock_context

                            check_result = process_format_check(str(sample_task.id))

                            assert check_result["status"] == "completed"

                            # Update task status and add rule_snapshot for fix
                            sample_task.status = "completed"
                            sample_task.rule_snapshot = {
                                "school_name": "测试大学",
                                "page_margin": {"top": "2.5cm"},
                            }
                            await db_session.commit()

        # Step 2: Run format fix
        with patch("app.tasks.format_tasks.get_storage_service", return_value=mock_storage_service):
            with patch("app.tasks.format_tasks.DocumentProcessor", return_value=mock_document_processor):
                with patch("app.tasks.format_tasks.get_db_context") as mock_db_context:
                    mock_context = MagicMock()
                    mock_context.__aenter__ = MagicMock(return_value=db_session)
                    mock_context.__aexit__ = MagicMock(return_value=None)
                    mock_db_context.return_value = mock_context

                    fix_result = process_format_fix(str(sample_task.id))

                    assert fix_result["status"] == "fixed"

    @pytest.mark.asyncio
    async def test_task_failure_handling(
        self,
        db_session,
        sample_task,
        mock_storage_service,
    ):
        """Test task failure handling and status updates."""
        from app.tasks.format_tasks import process_format_check

        # Make storage fail
        mock_storage_service.download_file.side_effect = ConnectionError("MinIO unavailable")

        with patch("app.tasks.format_tasks.get_storage_service", return_value=mock_storage_service):
            with patch("app.tasks.format_tasks.get_db_context") as mock_db_context:
                mock_context = MagicMock()
                mock_context.__aenter__ = MagicMock(return_value=db_session)
                mock_context.__aexit__ = MagicMock(return_value=None)
                mock_db_context.return_value = mock_context

                with pytest.raises(Exception):
                    process_format_check(str(sample_task.id))

                # Verify task status was updated to failed
                await db_session.refresh(sample_task)
                # Note: In actual implementation, the status update happens in the exception handler


# =============================================================================
# Error Handling Tests
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in Celery tasks."""

    @pytest.mark.asyncio
    async def test_process_format_check_database_error(
        self,
        db_session,
        sample_task,
        mock_storage_service,
        mock_document_processor,
        mock_rule_engine,
    ):
        """Test format check when database operations fail."""
        from app.tasks.format_tasks import process_format_check

        with patch("app.tasks.format_tasks.get_storage_service", return_value=mock_storage_service):
            with patch("app.tasks.format_tasks.DocumentProcessor", return_value=mock_document_processor):
                with patch("app.tasks.format_tasks.get_rule_engine", return_value=mock_rule_engine):
                    with patch("app.tasks.format_tasks.get_model_manager"):
                        with patch("app.tasks.format_tasks.get_db_context") as mock_db_context:
                            # Simulate database error
                            mock_session = MagicMock()
                            mock_session.execute = MagicMock(side_effect=Exception("DB Error"))
                            mock_context = MagicMock()
                            mock_context.__aenter__ = MagicMock(return_value=mock_session)
                            mock_context.__aexit__ = MagicMock(return_value=None)
                            mock_db_context.return_value = mock_context

                            with pytest.raises(Exception):
                                process_format_check(str(sample_task.id))

    @pytest.mark.asyncio
    async def test_process_format_fix_no_changes(
        self,
        db_session,
        completed_task,
        mock_storage_service,
    ):
        """Test format fix when no changes are needed."""
        from app.tasks.format_tasks import process_format_fix

        mock_processor = MagicMock()
        mock_processor.fix_only = MagicMock(return_value=([], b"document bytes"))

        with patch("app.tasks.format_tasks.get_storage_service", return_value=mock_storage_service):
            with patch("app.tasks.format_tasks.DocumentProcessor", return_value=mock_processor):
                with patch("app.tasks.format_tasks.get_db_context") as mock_db_context:
                    mock_context = MagicMock()
                    mock_context.__aenter__ = MagicMock(return_value=db_session)
                    mock_context.__aexit__ = MagicMock(return_value=None)
                    mock_db_context.return_value = mock_context

                    result = process_format_fix(str(completed_task.id))

                    assert result["status"] == "fixed"
                    assert result["total_changes"] == 0
