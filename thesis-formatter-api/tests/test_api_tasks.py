"""
Integration tests for Task API endpoints.

Tests for task endpoints using FastAPI TestClient and async SQLAlchemy.
Uses SQLite in-memory database for testing and mocks MinIO storage.
"""

import uuid
from datetime import datetime
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.main import create_application
from app.models import Change, Issue, Task


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
    mock.get_presigned_url = MagicMock(
        return_value="http://minio.test/presigned-url"
    )
    mock.delete_file = MagicMock(return_value=None)
    mock.file_exists = MagicMock(return_value=True)
    return mock


@pytest.fixture(scope="function")
def app(db_session, mock_storage_service):
    """Create FastAPI app with test dependencies."""
    app = create_application()

    # Override database dependency
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Mock storage service
    with patch(
        "app.api.v1.endpoints.tasks.get_storage_service",
        return_value=mock_storage_service,
    ):
        with patch(
            "app.api.v1.endpoints.tasks.process_format_check"
        ) as mock_celery:
            mock_celery.delay = MagicMock(return_value=None)
            yield app

    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(app):
    """Create synchronous test client."""
    return TestClient(app)


@pytest_asyncio.fixture(scope="function")
async def async_client(app):
    """Create asynchronous test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


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
async def completed_task(db_session):
    """Create a completed task with issues for testing."""
    task = Task(
        id=uuid.uuid4(),
        status="completed",
        thesis_file_key="thesis/test_thesis.docx",
        spec_file_key="spec/test_spec.pdf",
        template_id=None,
        model_id="test-model",
        rule_snapshot={
            "page_margin": {"top": "2.5cm", "bottom": "2.5cm"},
            "font": {"cn_body": "宋体"},
        },
        result_summary={
            "total_issues": 2,
            "error_count": 1,
            "warning_count": 1,
            "info_count": 0,
        },
        fixed_file_key="fixed/test_fixed.docx",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    # Add issues
    issue1 = Issue(
        id=uuid.uuid4(),
        task_id=task.id,
        severity="error",
        category="margin",
        location={"page": 1, "paragraph": 1},
        rule_id="margin_top",
        current_value="2.0cm",
        expected_value="2.5cm",
        suggestion="调整上边距为2.5cm",
        is_fixed=False,
    )
    issue2 = Issue(
        id=uuid.uuid4(),
        task_id=task.id,
        severity="warning",
        category="font",
        location={"page": 1, "paragraph": 2},
        rule_id="font_body",
        current_value="Arial",
        expected_value="Times New Roman",
        suggestion="使用Times New Roman字体",
        is_fixed=False,
    )
    db_session.add_all([issue1, issue2])
    await db_session.commit()

    return task


@pytest_asyncio.fixture(scope="function")
async def task_with_changes(db_session, completed_task):
    """Create a task with change records."""
    # Add changes
    change1 = Change(
        id=uuid.uuid4(),
        task_id=completed_task.id,
        issue_id=None,
        category="margin",
        location={"page": 1, "section": "header"},
        before_value="2.0cm",
        after_value="2.5cm",
        risk_level="low",
        created_at=datetime.utcnow(),
    )
    change2 = Change(
        id=uuid.uuid4(),
        task_id=completed_task.id,
        issue_id=None,
        category="font",
        location={"page": 1, "paragraph": 2},
        before_value="Arial",
        after_value="Times New Roman",
        risk_level="medium",
        created_at=datetime.utcnow(),
    )
    db_session.add_all([change1, change2])
    await db_session.commit()

    return completed_task


# =============================================================================
# Test Cases
# =============================================================================


class TestCreateTaskEndpoint:
    """Tests for POST /api/v1/tasks endpoint."""

    def test_create_task_with_valid_docx(self, client, mock_storage_service):
        """Test creating a task with valid .docx file."""
        # Create test file
        file_content = b"PK\x03\x04"  # Minimal ZIP/DOCX header
        files = {
            "thesis_file": ("test_thesis.docx", BytesIO(file_content), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        }

        response = client.post("/api/v1/tasks", files=files)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending"
        assert "created_at" in data

        # Verify storage service was called
        mock_storage_service.ensure_bucket.assert_called_once()
        mock_storage_service.upload_file.assert_called_once()

    def test_create_task_with_spec_file(self, client, mock_storage_service):
        """Test creating a task with both thesis and spec files."""
        thesis_content = b"PK\x03\x04"
        spec_content = b"Test spec content"

        files = {
            "thesis_file": ("thesis.docx", BytesIO(thesis_content), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            "spec_file": ("spec.pdf", BytesIO(spec_content), "application/pdf"),
        }

        response = client.post("/api/v1/tasks", files=files)

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"

        # Verify both files were uploaded
        assert mock_storage_service.upload_file.call_count == 2

    def test_create_task_with_template_id(self, client, mock_storage_service):
        """Test creating a task with template_id parameter."""
        file_content = b"PK\x03\x04"
        files = {
            "thesis_file": ("thesis.docx", BytesIO(file_content), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        }
        data = {"template_id": str(uuid.uuid4())}

        response = client.post("/api/v1/tasks", files=files, data=data)

        assert response.status_code == 201

    def test_create_task_with_model_id(self, client, mock_storage_service):
        """Test creating a task with model_id parameter."""
        file_content = b"PK\x03\x04"
        files = {
            "thesis_file": ("thesis.docx", BytesIO(file_content), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        }
        data = {"model_id": "deepseek-chat"}

        response = client.post("/api/v1/tasks", files=files, data=data)

        assert response.status_code == 201

    def test_create_task_invalid_file_extension(self, client):
        """Test creating a task with invalid file extension."""
        file_content = b"Invalid content"
        files = {
            "thesis_file": ("thesis.pdf", BytesIO(file_content), "application/pdf"),
        }

        response = client.post("/api/v1/tasks", files=files)

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert ".docx" in data["detail"]

    def test_create_task_missing_file(self, client):
        """Test creating a task without required thesis file."""
        response = client.post("/api/v1/tasks")

        assert response.status_code == 422  # Validation error

    def test_create_task_storage_service_unavailable(self, client, mock_storage_service):
        """Test creating a task when storage service is unavailable."""
        mock_storage_service.ensure_bucket.side_effect = ConnectionError("MinIO unavailable")

        file_content = b"PK\x03\x04"
        files = {
            "thesis_file": ("thesis.docx", BytesIO(file_content), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        }

        response = client.post("/api/v1/tasks", files=files)

        assert response.status_code == 503
        data = response.json()
        assert "存储服务" in data["detail"] or "storage" in data["detail"].lower()


class TestGetTaskStatusEndpoint:
    """Tests for GET /api/v1/tasks/{task_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_task_status_success(self, async_client, sample_task):
        """Test getting status of an existing task."""
        response = await async_client.get(f"/api/v1/tasks/{sample_task.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_task.id)
        assert data["status"] == "pending"
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_get_task_status_with_issues(self, async_client, completed_task):
        """Test getting status of a completed task with issues."""
        response = await async_client.get(f"/api/v1/tasks/{completed_task.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(completed_task.id)
        assert data["status"] == "completed"
        assert data["issue_count"] == 2
        assert data["fix_available"] is True

    @pytest.mark.asyncio
    async def test_get_task_status_not_found(self, async_client):
        """Test getting status of non-existent task."""
        fake_id = uuid.uuid4()
        response = await async_client.get(f"/api/v1/tasks/{fake_id}")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_get_task_status_invalid_uuid(self, async_client):
        """Test getting status with invalid UUID format."""
        response = await async_client.get("/api/v1/tasks/invalid-uuid")

        assert response.status_code == 422  # Validation error


class TestGetTaskReportEndpoint:
    """Tests for GET /api/v1/tasks/{task_id}/report endpoint."""

    @pytest.mark.asyncio
    async def test_get_task_report_success(self, async_client, completed_task):
        """Test getting report for a completed task."""
        response = await async_client.get(f"/api/v1/tasks/{completed_task.id}/report")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == str(completed_task.id)
        assert "summary" in data
        assert "issues" in data
        assert "rules_applied" in data
        assert len(data["issues"]) == 2

    @pytest.mark.asyncio
    async def test_get_task_report_not_completed(self, async_client, sample_task):
        """Test getting report for a task that is not completed."""
        response = await async_client.get(f"/api/v1/tasks/{sample_task.id}/report")

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "尚未完成" in data["detail"] or "completed" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_task_report_not_found(self, async_client):
        """Test getting report for non-existent task."""
        fake_id = uuid.uuid4()
        response = await async_client.get(f"/api/v1/tasks/{fake_id}/report")

        assert response.status_code == 404


class TestFixTaskEndpoint:
    """Tests for POST /api/v1/tasks/{task_id}/fix endpoint."""

    @pytest.mark.asyncio
    async def test_fix_task_success(self, async_client, completed_task):
        """Test fixing a completed task."""
        with patch(
            "app.api.v1.endpoints.tasks.process_format_fix"
        ) as mock_fix_task:
            mock_fix_task.delay = MagicMock(return_value=None)

            response = await async_client.post(f"/api/v1/tasks/{completed_task.id}/fix")

            assert response.status_code == 200
            data = response.json()
            assert data["message"] == "修复任务已启动"
            assert data["task_id"] == str(completed_task.id)

            # Verify Celery task was triggered
            mock_fix_task.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_fix_task_with_issue_ids(self, async_client, completed_task):
        """Test fixing specific issues."""
        with patch(
            "app.api.v1.endpoints.tasks.process_format_fix"
        ) as mock_fix_task:
            mock_fix_task.delay = MagicMock(return_value=None)

            # Get issue IDs
            issue_ids = [str(issue.id) for issue in completed_task.issues]

            response = await async_client.post(
                f"/api/v1/tasks/{completed_task.id}/fix",
                json=issue_ids,
            )

            assert response.status_code == 200
            mock_fix_task.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_fix_task_not_completed(self, async_client, sample_task):
        """Test fixing a task that is not completed."""
        response = await async_client.post(f"/api/v1/tasks/{sample_task.id}/fix")

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_fix_task_not_found(self, async_client):
        """Test fixing non-existent task."""
        fake_id = uuid.uuid4()
        response = await async_client.post(f"/api/v1/tasks/{fake_id}/fix")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_fix_task_celery_unavailable(self, async_client, completed_task):
        """Test fixing when Celery is unavailable."""
        with patch(
            "app.api.v1.endpoints.tasks.process_format_fix"
        ) as mock_fix_task:
            mock_fix_task.delay.side_effect = Exception("Celery unavailable")

            response = await async_client.post(f"/api/v1/tasks/{completed_task.id}/fix")

            assert response.status_code == 503
            data = response.json()
            assert "detail" in data


class TestDownloadEndpoint:
    """Tests for GET /api/v1/tasks/{task_id}/download endpoint."""

    @pytest.mark.asyncio
    async def test_download_success(self, async_client, completed_task, mock_storage_service):
        """Test downloading fixed document."""
        response = await async_client.get(f"/api/v1/tasks/{completed_task.id}/download")

        assert response.status_code == 200
        data = response.json()
        assert "download_url" in data
        assert "file_name" in data
        assert data["download_url"] == "http://minio.test/presigned-url"

        mock_storage_service.get_presigned_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_no_fixed_file(self, async_client, sample_task):
        """Test downloading when fixed file is not available."""
        response = await async_client.get(f"/api/v1/tasks/{sample_task.id}/download")

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "尚未生成" in data["detail"] or "not" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_download_not_found(self, async_client):
        """Test downloading for non-existent task."""
        fake_id = uuid.uuid4()
        response = await async_client.get(f"/api/v1/tasks/{fake_id}/download")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_download_storage_error(self, async_client, completed_task, mock_storage_service):
        """Test downloading when storage service fails."""
        mock_storage_service.get_presigned_url.side_effect = ConnectionError("MinIO error")

        response = await async_client.get(f"/api/v1/tasks/{completed_task.id}/download")

        assert response.status_code == 503


class TestChangelogEndpoint:
    """Tests for GET /api/v1/tasks/{task_id}/changelog endpoint."""

    @pytest.mark.asyncio
    async def test_changelog_success(self, async_client, task_with_changes):
        """Test getting changelog for a task with changes."""
        response = await async_client.get(f"/api/v1/tasks/{task_with_changes.id}/changelog")

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == str(task_with_changes.id)
        assert data["total_changes"] == 2
        assert len(data["changes"]) == 2

        # Verify change record structure
        change = data["changes"][0]
        assert "id" in change
        assert "category" in change
        assert "location" in change
        assert "before_value" in change
        assert "after_value" in change
        assert "risk_level" in change
        assert "created_at" in change

    @pytest.mark.asyncio
    async def test_changelog_empty(self, async_client, completed_task):
        """Test getting changelog for a task without changes."""
        response = await async_client.get(f"/api/v1/tasks/{completed_task.id}/changelog")

        assert response.status_code == 200
        data = response.json()
        assert data["total_changes"] == 0
        assert data["changes"] == []

    @pytest.mark.asyncio
    async def test_changelog_not_found(self, async_client):
        """Test getting changelog for non-existent task."""
        fake_id = uuid.uuid4()
        response = await async_client.get(f"/api/v1/tasks/{fake_id}/changelog")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_changelog_ordered_by_time(self, async_client, db_session, completed_task):
        """Test that changelog is ordered by created_at."""
        # Add changes with different timestamps
        from datetime import timedelta

        change1 = Change(
            id=uuid.uuid4(),
            task_id=completed_task.id,
            category="margin",
            location={"page": 1},
            before_value="old",
            after_value="new",
            risk_level="low",
            created_at=datetime.utcnow() - timedelta(hours=2),
        )
        change2 = Change(
            id=uuid.uuid4(),
            task_id=completed_task.id,
            category="font",
            location={"page": 2},
            before_value="old2",
            after_value="new2",
            risk_level="high",
            created_at=datetime.utcnow() - timedelta(hours=1),
        )
        db_session.add_all([change1, change2])
        await db_session.commit()

        response = await async_client.get(f"/api/v1/tasks/{completed_task.id}/changelog")

        assert response.status_code == 200
        data = response.json()
        changes = data["changes"]

        # Verify ascending order by created_at
        for i in range(len(changes) - 1):
            assert changes[i]["created_at"] <= changes[i + 1]["created_at"]


# =============================================================================
# Additional Edge Case Tests
# =============================================================================


class TestTaskEdgeCases:
    """Edge case tests for task endpoints."""

    @pytest.mark.asyncio
    async def test_concurrent_task_creation(self, async_client, mock_storage_service):
        """Test creating multiple tasks concurrently."""
        import asyncio

        async def create_task():
            file_content = b"PK\x03\x04"
            files = {
                "thesis_file": ("thesis.docx", BytesIO(file_content), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            }
            return await async_client.post("/api/v1/tasks", files=files)

        # Create 5 tasks concurrently
        responses = await asyncio.gather(*[create_task() for _ in range(5)])

        # All should succeed
        for response in responses:
            assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_task_status_transitions(self, async_client, db_session):
        """Test task status transitions."""
        # Create a task
        task = Task(
            id=uuid.uuid4(),
            status="pending",
            thesis_file_key="thesis/test.docx",
            created_at=datetime.utcnow(),
        )
        db_session.add(task)
        await db_session.commit()

        # Check initial status
        response = await async_client.get(f"/api/v1/tasks/{task.id}")
        assert response.json()["status"] == "pending"

        # Update status to processing
        task.status = "processing"
        await db_session.commit()

        response = await async_client.get(f"/api/v1/tasks/{task.id}")
        assert response.json()["status"] == "processing"

        # Update status to completed
        task.status = "completed"
        await db_session.commit()

        response = await async_client.get(f"/api/v1/tasks/{task.id}")
        assert response.json()["status"] == "completed"
