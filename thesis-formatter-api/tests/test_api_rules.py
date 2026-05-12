"""
Integration tests for Rule API endpoints.

Tests for rule endpoints including parsing, listing, creating, and updating rules.
Uses SQLite in-memory database for testing and mocks MinIO storage and AI parsing.
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
from app.models import Rule


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
    mock.upload_file = MagicMock(return_value="test_spec_key")
    mock.download_file = MagicMock(return_value=b"Test specification content")
    mock.delete_file = MagicMock(return_value=None)
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
        "font_size": {
            "body": "12pt",
            "heading1": "22pt",
        },
        "line_spacing": {
            "body": "1.5倍",
        },
    })
    return mock


@pytest.fixture(scope="function")
def mock_rule_engine():
    """Create mock rule engine."""
    mock = MagicMock()
    mock.validate_rules = MagicMock(return_value=[])
    mock.get_default_rules = MagicMock(return_value={
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
def app(db_session, mock_storage_service, mock_spec_parser, mock_rule_engine):
    """Create FastAPI app with test dependencies."""
    app = create_application()

    # Override database dependency
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Mock services
    with patch(
        "app.api.v1.endpoints.rules.get_storage_service",
        return_value=mock_storage_service,
    ):
        with patch(
            "app.api.v1.endpoints.rules.SpecParser",
            return_value=mock_spec_parser,
        ):
            with patch(
                "app.api.v1.endpoints.rules.get_rule_engine",
                return_value=mock_rule_engine,
            ):
                with patch(
                    "app.api.v1.endpoints.rules.get_model_manager",
                ) as mock_model_manager:
                    mock_manager = MagicMock()
                    mock_manager.has_providers = True
                    mock_model_manager.return_value = mock_manager
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
async def sample_rules(db_session):
    """Create sample rules for testing."""
    rules = []
    for i in range(3):
        rule = Rule(
            id=uuid.uuid4(),
            name=f"测试规则 {i+1}",
            source="manual" if i % 2 == 0 else "ai_parsed",
            rule_data={
                "school_name": f"学校{i+1}",
                "page_margin": {"top": "2.5cm", "bottom": "2.5cm"},
                "font": {"cn_body": "宋体"},
            },
            school_name=f"学校{i+1}",
            is_active=True,
            created_at=datetime.utcnow(),
        )
        rules.append(rule)

    # Add an inactive rule
    inactive_rule = Rule(
        id=uuid.uuid4(),
        name="未激活规则",
        source="manual",
        rule_data={"school_name": "测试学校"},
        school_name="测试学校",
        is_active=False,
        created_at=datetime.utcnow(),
    )
    rules.append(inactive_rule)

    db_session.add_all(rules)
    await db_session.commit()
    return rules


@pytest_asyncio.fixture(scope="function")
async def sample_rule(db_session):
    """Create a single sample rule for testing."""
    rule = Rule(
        id=uuid.uuid4(),
        name="清华大学硕士论文格式",
        source="manual",
        rule_data={
            "school_name": "清华大学",
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
        },
        school_name="清华大学",
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db_session.add(rule)
    await db_session.commit()
    await db_session.refresh(rule)
    return rule


# =============================================================================
# Test Cases
# =============================================================================


class TestParseRuleFileEndpoint:
    """Tests for POST /api/v1/rules/parse endpoint."""

    def test_parse_rule_file_with_pdf(self, client, mock_storage_service):
        """Test parsing a PDF specification file."""
        file_content = b"PDF content"
        files = {
            "spec_file": ("spec.pdf", BytesIO(file_content), "application/pdf"),
        }

        response = client.post("/api/v1/rules/parse", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "规范解析成功"
        assert "rule_id" in data
        assert "rules" in data
        assert data["file_name"] == "spec.pdf"

        # Verify storage service was called
        mock_storage_service.ensure_bucket.assert_called_once()
        mock_storage_service.upload_file.assert_called_once()

    def test_parse_rule_file_with_docx(self, client, mock_storage_service):
        """Test parsing a DOCX specification file."""
        file_content = b"DOCX content"
        files = {
            "spec_file": ("spec.docx", BytesIO(file_content), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
        }

        response = client.post("/api/v1/rules/parse", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "规范解析成功"
        assert data["file_name"] == "spec.docx"

    def test_parse_rule_file_with_txt(self, client, mock_storage_service):
        """Test parsing a TXT specification file."""
        file_content = b"Text specification content"
        files = {
            "spec_file": ("spec.txt", BytesIO(file_content), "text/plain"),
        }

        response = client.post("/api/v1/rules/parse", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "规范解析成功"
        assert data["file_name"] == "spec.txt"

    def test_parse_rule_file_with_model_id(self, client, mock_storage_service):
        """Test parsing with specific model_id."""
        file_content = b"PDF content"
        files = {
            "spec_file": ("spec.pdf", BytesIO(file_content), "application/pdf"),
        }
        params = {"model_id": "deepseek-chat"}

        response = client.post("/api/v1/rules/parse", files=files, params=params)

        assert response.status_code == 200
        data = response.json()
        assert data["model_id"] == "deepseek-chat"

    def test_parse_rule_file_missing_file(self, client):
        """Test parsing without providing a file."""
        response = client.post("/api/v1/rules/parse")

        assert response.status_code == 422  # Validation error

    def test_parse_rule_file_empty_filename(self, client):
        """Test parsing with empty filename."""
        files = {
            "spec_file": ("", BytesIO(b"content"), "application/pdf"),
        }

        response = client.post("/api/v1/rules/parse", files=files)

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data

    def test_parse_rule_file_storage_unavailable(self, client, mock_storage_service):
        """Test parsing when storage service is unavailable."""
        mock_storage_service.ensure_bucket.side_effect = ConnectionError("MinIO unavailable")

        file_content = b"PDF content"
        files = {
            "spec_file": ("spec.pdf", BytesIO(file_content), "application/pdf"),
        }

        response = client.post("/api/v1/rules/parse", files=files)

        assert response.status_code == 503
        data = response.json()
        assert "存储服务" in data["detail"] or "storage" in data["detail"].lower()

    def test_parse_rule_file_with_validation_warnings(self, client, mock_storage_service, mock_rule_engine):
        """Test parsing when rules have validation warnings."""
        mock_rule_engine.validate_rules.return_value = ["Missing required field: font_size"]

        file_content = b"PDF content"
        files = {
            "spec_file": ("spec.pdf", BytesIO(file_content), "application/pdf"),
        }

        response = client.post("/api/v1/rules/parse", files=files)

        assert response.status_code == 200
        data = response.json()
        assert "validation_warnings" in data
        assert data["validation_warnings"] is not None


class TestListRulesEndpoint:
    """Tests for GET /api/v1/rules endpoint."""

    @pytest.mark.asyncio
    async def test_list_rules_success(self, async_client, sample_rules):
        """Test listing all active rules."""
        response = await async_client.get("/api/v1/rules")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3  # Only active rules

        # Verify rule structure
        rule = data[0]
        assert "id" in rule
        assert "name" in rule
        assert "source" in rule
        assert "rule_data" in rule
        assert "school_name" in rule
        assert "is_active" in rule
        assert "created_at" in rule

    @pytest.mark.asyncio
    async def test_list_rules_include_inactive(self, async_client, sample_rules):
        """Test listing all rules including inactive."""
        response = await async_client.get("/api/v1/rules?is_active=false")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1  # Only inactive rules
        assert data[0]["name"] == "未激活规则"

    @pytest.mark.asyncio
    async def test_list_rules_filter_by_school_name(self, async_client, sample_rules):
        """Test filtering rules by school name."""
        response = await async_client.get("/api/v1/rules?school_name=学校1")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["school_name"] == "学校1"

    @pytest.mark.asyncio
    async def test_list_rules_filter_partial_school_name(self, async_client, sample_rules):
        """Test filtering rules with partial school name match."""
        response = await async_client.get("/api/v1/rules?school_name=学校")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3  # All active rules have "学校" in name

    @pytest.mark.asyncio
    async def test_list_rules_empty_result(self, async_client, sample_rules):
        """Test filtering with no matching rules."""
        response = await async_client.get("/api/v1/rules?school_name=不存在的学校")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_list_rules_ordered_by_created_at(self, async_client, db_session):
        """Test that rules are ordered by created_at desc."""
        from datetime import timedelta

        # Create rules with different timestamps
        for i in range(3):
            rule = Rule(
                id=uuid.uuid4(),
                name=f"顺序规则 {i}",
                source="manual",
                rule_data={},
                school_name="测试",
                is_active=True,
                created_at=datetime.utcnow() - timedelta(hours=i),
            )
            db_session.add(rule)
        await db_session.commit()

        response = await async_client.get("/api/v1/rules")

        assert response.status_code == 200
        data = response.json()

        # Verify descending order
        for i in range(len(data) - 1):
            assert data[i]["created_at"] >= data[i + 1]["created_at"]


class TestCreateRuleEndpoint:
    """Tests for POST /api/v1/rules endpoint."""

    @pytest.mark.asyncio
    async def test_create_rule_success(self, async_client):
        """Test creating a new rule."""
        rule_data = {
            "name": "北京大学博士论文格式",
            "source": "manual",
            "rule_data": {
                "school_name": "北京大学",
                "thesis_type": "doctor",
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
            },
            "school_name": "北京大学",
        }

        response = await async_client.post("/api/v1/rules", json=rule_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == rule_data["name"]
        assert data["source"] == rule_data["source"]
        assert data["school_name"] == rule_data["school_name"]
        assert "id" in data
        assert "created_at" in data
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_create_rule_minimal_data(self, async_client):
        """Test creating a rule with minimal data."""
        rule_data = {
            "name": "最小规则",
            "rule_data": {
                "school_name": "测试学校",
            },
        }

        response = await async_client.post("/api/v1/rules", json=rule_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "最小规则"
        assert data["source"] == "manual"  # Default value
        assert data["school_name"] is None  # Optional field

    @pytest.mark.asyncio
    async def test_create_rule_ai_parsed_source(self, async_client):
        """Test creating a rule with ai_parsed source."""
        rule_data = {
            "name": "AI解析规则",
            "source": "ai_parsed",
            "rule_data": {
                "school_name": "AI大学",
                "page_margin": {"top": "2.5cm"},
            },
            "school_name": "AI大学",
        }

        response = await async_client.post("/api/v1/rules", json=rule_data)

        assert response.status_code == 201
        data = response.json()
        assert data["source"] == "ai_parsed"

    @pytest.mark.asyncio
    async def test_create_rule_invalid_data(self, async_client):
        """Test creating a rule with invalid data."""
        rule_data = {
            # Missing required "name" field
            "rule_data": {},
        }

        response = await async_client.post("/api/v1/rules", json=rule_data)

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_create_rule_complex_rule_data(self, async_client):
        """Test creating a rule with complex nested rule_data."""
        rule_data = {
            "name": "复杂格式规则",
            "source": "manual",
            "school_name": "综合大学",
            "rule_data": {
                "school_name": "综合大学",
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
                    "cn_heading": "黑体",
                    "en_heading": "Arial",
                },
                "font_size": {
                    "body": "12pt",
                    "heading1": "22pt",
                    "heading2": "16pt",
                    "heading3": "14pt",
                },
                "line_spacing": {
                    "body": "1.5倍",
                    "heading": "单倍",
                },
                "paragraph_spacing": {
                    "body": {"before": "0pt", "after": "0pt"},
                },
                "heading_style": {
                    "heading1": {"font": "黑体", "bold": True},
                    "heading2": {"font": "黑体", "bold": True},
                },
                "page_number": {
                    "position": "bottom_center",
                    "format": "arabic",
                },
                "references": {
                    "indent": "hanging",
                },
            },
        }

        response = await async_client.post("/api/v1/rules", json=rule_data)

        assert response.status_code == 201
        data = response.json()
        assert data["rule_data"]["font_size"]["heading1"] == "22pt"
        assert data["rule_data"]["heading_style"]["heading1"]["bold"] is True


class TestUpdateRuleEndpoint:
    """Tests for PUT /api/v1/rules/{rule_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_rule_success(self, async_client, sample_rule):
        """Test updating an existing rule."""
        update_data = {
            "name": "清华大学硕士论文格式（更新版）",
            "source": "manual",
            "rule_data": {
                "school_name": "清华大学",
                "thesis_type": "master",
                "page_margin": {
                    "top": "2.6cm",  # Changed
                    "bottom": "2.6cm",  # Changed
                    "left": "3.0cm",
                    "right": "2.5cm",
                },
                "font": {
                    "cn_body": "宋体",
                    "en_body": "Times New Roman",
                },
            },
            "school_name": "清华大学",
        }

        response = await async_client.put(
            f"/api/v1/rules/{sample_rule.id}", json=update_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["rule_data"]["page_margin"]["top"] == "2.6cm"

    @pytest.mark.asyncio
    async def test_update_rule_not_found(self, async_client):
        """Test updating a non-existent rule."""
        fake_id = uuid.uuid4()
        update_data = {
            "name": "不存在的规则",
            "rule_data": {"school_name": "测试"},
        }

        response = await async_client.put(f"/api/v1/rules/{fake_id}", json=update_data)

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_update_rule_partial_data(self, async_client, sample_rule):
        """Test updating a rule with partial data."""
        update_data = {
            "name": "仅更新名称",
            "source": "manual",
            "rule_data": {
                "school_name": "清华大学",
                "new_field": "新值",
            },
            "school_name": "清华大学",
        }

        response = await async_client.put(
            f"/api/v1/rules/{sample_rule.id}", json=update_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "仅更新名称"
        assert data["rule_data"]["new_field"] == "新值"

    @pytest.mark.asyncio
    async def test_update_rule_invalid_uuid(self, async_client):
        """Test updating with invalid UUID format."""
        update_data = {"name": "测试", "rule_data": {}}

        response = await async_client.put("/api/v1/rules/invalid-uuid", json=update_data)

        assert response.status_code == 422  # Validation error


class TestGetRuleEndpoint:
    """Tests for GET /api/v1/rules/{rule_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_rule_success(self, async_client, sample_rule):
        """Test getting a specific rule."""
        response = await async_client.get(f"/api/v1/rules/{sample_rule.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_rule.id)
        assert data["name"] == sample_rule.name
        assert data["school_name"] == sample_rule.school_name

    @pytest.mark.asyncio
    async def test_get_rule_not_found(self, async_client):
        """Test getting a non-existent rule."""
        fake_id = uuid.uuid4()
        response = await async_client.get(f"/api/v1/rules/{fake_id}")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_get_rule_invalid_uuid(self, async_client):
        """Test getting with invalid UUID format."""
        response = await async_client.get("/api/v1/rules/invalid-uuid")

        assert response.status_code == 422  # Validation error


class TestDeleteRuleEndpoint:
    """Tests for DELETE /api/v1/rules/{rule_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_rule_success(self, async_client, sample_rule, db_session):
        """Test deleting a rule."""
        response = await async_client.delete(f"/api/v1/rules/{sample_rule.id}")

        assert response.status_code == 204

        # Verify rule is deleted
        from sqlalchemy import select

        result = await db_session.execute(select(Rule).where(Rule.id == sample_rule.id))
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_rule_not_found(self, async_client):
        """Test deleting a non-existent rule."""
        fake_id = uuid.uuid4()
        response = await async_client.delete(f"/api/v1/rules/{fake_id}")

        assert response.status_code == 404


# =============================================================================
# Additional Edge Case Tests
# =============================================================================


class TestRuleEdgeCases:
    """Edge case tests for rule endpoints."""

    @pytest.mark.asyncio
    async def test_create_rule_with_empty_rule_data(self, async_client):
        """Test creating a rule with empty rule_data."""
        rule_data = {
            "name": "空规则",
            "rule_data": {},
        }

        response = await async_client.post("/api/v1/rules", json=rule_data)

        assert response.status_code == 201
        data = response.json()
        assert data["rule_data"] == {}

    @pytest.mark.asyncio
    async def test_create_rule_with_unicode_name(self, async_client):
        """Test creating a rule with unicode characters in name."""
        rule_data = {
            "name": "🎓 论文格式规则（测试版）v1.0",
            "rule_data": {"school_name": "测试大学"},
        }

        response = await async_client.post("/api/v1/rules", json=rule_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == rule_data["name"]

    @pytest.mark.asyncio
    async def test_list_rules_case_insensitive_school_name(self, async_client, db_session):
        """Test that school name filtering is case insensitive."""
        # Create rules with different case
        rule1 = Rule(
            id=uuid.uuid4(),
            name="规则1",
            source="manual",
            rule_data={},
            school_name="Beijing University",
            is_active=True,
            created_at=datetime.utcnow(),
        )
        rule2 = Rule(
            id=uuid.uuid4(),
            name="规则2",
            source="manual",
            rule_data={},
            school_name="BEIJING UNIVERSITY",
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db_session.add_all([rule1, rule2])
        await db_session.commit()

        response = await async_client.get("/api/v1/rules?school_name=beijing")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    @pytest.mark.asyncio
    async def test_concurrent_rule_creation(self, async_client):
        """Test creating multiple rules concurrently."""
        import asyncio

        async def create_rule(i):
            rule_data = {
                "name": f"并发规则 {i}",
                "rule_data": {"school_name": f"学校{i}"},
            }
            return await async_client.post("/api/v1/rules", json=rule_data)

        # Create 5 rules concurrently
        responses = await asyncio.gather(*[create_rule(i) for i in range(5)])

        # All should succeed
        for response in responses:
            assert response.status_code == 201

        # Verify all rules were created
        list_response = await async_client.get("/api/v1/rules")
        data = list_response.json()
        assert len(data) == 5

    @pytest.mark.asyncio
    async def test_update_rule_preserves_id(self, async_client, sample_rule):
        """Test that updating a rule preserves its ID."""
        original_id = sample_rule.id

        update_data = {
            "name": "更新后的名称",
            "source": "manual",
            "rule_data": {"school_name": "清华大学"},
            "school_name": "清华大学",
        }

        response = await async_client.put(
            f"/api/v1/rules/{sample_rule.id}", json=update_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(original_id)
