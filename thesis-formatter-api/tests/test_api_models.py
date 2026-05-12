"""
Integration tests for Model API endpoints.

Tests for model configuration endpoints including listing, configuring, updating,
and testing AI models. Uses SQLite in-memory database for testing.
"""

import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base, get_db
from app.main import create_application
from app.models import ModelConfig


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
def mock_model_manager():
    """Create mock model manager."""
    mock = MagicMock()
    mock.register = MagicMock(return_value=None)
    return mock


@pytest.fixture(scope="function")
def app(db_session, mock_model_manager):
    """Create FastAPI app with test dependencies."""
    app = create_application()

    # Override database dependency
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Mock model manager
    with patch(
        "app.api.v1.endpoints.models.get_model_manager",
        return_value=mock_model_manager,
    ):
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
async def sample_models(db_session):
    """Create sample model configurations for testing."""
    models = []

    # DeepSeek model
    model1 = ModelConfig(
        id=uuid.uuid4(),
        name="DeepSeek-V3",
        provider="deepseek",
        api_key_encrypted="encrypted_key_1",
        base_url="https://api.deepseek.com/v1",
        model_name="deepseek-chat",
        is_default=True,
        priority=1,
        created_at=datetime.utcnow(),
    )
    models.append(model1)

    # OpenAI model
    model2 = ModelConfig(
        id=uuid.uuid4(),
        name="GPT-4o",
        provider="openai",
        api_key_encrypted="encrypted_key_2",
        base_url="https://api.openai.com/v1",
        model_name="gpt-4o",
        is_default=False,
        priority=2,
        created_at=datetime.utcnow(),
    )
    models.append(model2)

    # Qwen model
    model3 = ModelConfig(
        id=uuid.uuid4(),
        name="Qwen-Max",
        provider="qwen",
        api_key_encrypted="encrypted_key_3",
        base_url="https://dashscope.aliyuncs.com/v1",
        model_name="qwen-max",
        is_default=False,
        priority=3,
        created_at=datetime.utcnow(),
    )
    models.append(model3)

    db_session.add_all(models)
    await db_session.commit()
    return models


@pytest_asyncio.fixture(scope="function")
async def sample_model(db_session):
    """Create a single sample model for testing."""
    model = ModelConfig(
        id=uuid.uuid4(),
        name="Test Model",
        provider="custom",
        api_key_encrypted="encrypted_test_key",
        base_url="https://api.example.com/v1",
        model_name="test-model",
        is_default=False,
        priority=1,
        created_at=datetime.utcnow(),
    )
    db_session.add(model)
    await db_session.commit()
    await db_session.refresh(model)
    return model


# =============================================================================
# Test Cases
# =============================================================================


class TestListModelsEndpoint:
    """Tests for GET /api/v1/models endpoint."""

    @pytest.mark.asyncio
    async def test_list_models_success(self, async_client, sample_models):
        """Test listing all model configurations."""
        response = await async_client.get("/api/v1/models")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

        # Verify model structure
        model = data[0]
        assert "id" in model
        assert "name" in model
        assert "provider" in model
        assert "base_url" in model
        assert "model_name" in model
        assert "is_default" in model
        assert "priority" in model
        assert "created_at" in model

        # Verify API key is not exposed
        assert "api_key" not in model
        assert "api_key_encrypted" not in model

    @pytest.mark.asyncio
    async def test_list_models_ordered_by_priority(self, async_client, sample_models):
        """Test that models are ordered by priority."""
        response = await async_client.get("/api/v1/models")

        assert response.status_code == 200
        data = response.json()

        # Verify ascending order by priority
        priorities = [m["priority"] for m in data]
        assert priorities == sorted(priorities)

    @pytest.mark.asyncio
    async def test_list_models_filter_by_provider(self, async_client, sample_models):
        """Test filtering models by provider."""
        response = await async_client.get("/api/v1/models?provider=deepseek")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["provider"] == "deepseek"
        assert data[0]["name"] == "DeepSeek-V3"

    @pytest.mark.asyncio
    async def test_list_models_filter_no_match(self, async_client, sample_models):
        """Test filtering with no matching provider."""
        response = await async_client.get("/api/v1/models?provider=nonexistent")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_list_models_empty_database(self, async_client):
        """Test listing models when database is empty."""
        response = await async_client.get("/api/v1/models")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_list_models_default_flag(self, async_client, sample_models):
        """Test that default model is correctly identified."""
        response = await async_client.get("/api/v1/models")

        assert response.status_code == 200
        data = response.json()

        # Find default model
        default_models = [m for m in data if m["is_default"]]
        assert len(default_models) == 1
        assert default_models[0]["name"] == "DeepSeek-V3"


class TestConfigureModelEndpoint:
    """Tests for POST /api/v1/models/config endpoint."""

    @pytest.mark.asyncio
    async def test_configure_model_success(self, async_client, mock_model_manager):
        """Test configuring a new model."""
        config_data = {
            "name": "Claude-3",
            "api_key": "sk-test-api-key",
            "base_url": "https://api.anthropic.com/v1",
            "model_name": "claude-3-opus-20240229",
            "is_default": False,
        }

        response = await async_client.post("/api/v1/models/config", json=config_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == config_data["name"]
        assert data["provider"] == "custom"  # Auto-detected from base_url
        assert data["base_url"] == config_data["base_url"]
        assert data["model_name"] == config_data["model_name"]
        assert data["is_default"] is False
        assert "id" in data
        assert "priority" in data
        assert "created_at" in data

        # Verify model manager was called
        mock_model_manager.register.assert_called_once()

    @pytest.mark.asyncio
    async def test_configure_model_deepseek_provider(self, async_client, mock_model_manager):
        """Test configuring DeepSeek model (provider auto-detection)."""
        config_data = {
            "name": "DeepSeek-V3",
            "api_key": "sk-deepseek-key",
            "base_url": "https://api.deepseek.com/v1",
            "model_name": "deepseek-chat",
            "is_default": False,
        }

        response = await async_client.post("/api/v1/models/config", json=config_data)

        assert response.status_code == 201
        data = response.json()
        assert data["provider"] == "deepseek"

    @pytest.mark.asyncio
    async def test_configure_model_openai_provider(self, async_client, mock_model_manager):
        """Test configuring OpenAI model (provider auto-detection)."""
        config_data = {
            "name": "GPT-4o",
            "api_key": "sk-openai-key",
            "base_url": "https://api.openai.com/v1",
            "model_name": "gpt-4o",
            "is_default": False,
        }

        response = await async_client.post("/api/v1/models/config", json=config_data)

        assert response.status_code == 201
        data = response.json()
        assert data["provider"] == "openai"

    @pytest.mark.asyncio
    async def test_configure_model_qwen_provider(self, async_client, mock_model_manager):
        """Test configuring Qwen model (provider auto-detection)."""
        config_data = {
            "name": "Qwen-Max",
            "api_key": "sk-qwen-key",
            "base_url": "https://dashscope.aliyuncs.com/v1",
            "model_name": "qwen-max",
            "is_default": False,
        }

        response = await async_client.post("/api/v1/models/config", json=config_data)

        assert response.status_code == 201
        data = response.json()
        assert data["provider"] == "qwen"

    @pytest.mark.asyncio
    async def test_configure_model_ollama_provider(self, async_client, mock_model_manager):
        """Test configuring Ollama model (provider auto-detection)."""
        config_data = {
            "name": "Local Llama",
            "api_key": "",
            "base_url": "http://localhost:11434/v1",
            "model_name": "llama2",
            "is_default": False,
        }

        response = await async_client.post("/api/v1/models/config", json=config_data)

        assert response.status_code == 201
        data = response.json()
        assert data["provider"] == "ollama"

    @pytest.mark.asyncio
    async def test_configure_model_siliconflow_provider(self, async_client, mock_model_manager):
        """Test configuring SiliconFlow model (provider auto-detection)."""
        config_data = {
            "name": "SiliconFlow Model",
            "api_key": "sk-siliconflow-key",
            "base_url": "https://api.siliconflow.cn/v1",
            "model_name": "deepseek-ai/DeepSeek-V3",
            "is_default": False,
        }

        response = await async_client.post("/api/v1/models/config", json=config_data)

        assert response.status_code == 201
        data = response.json()
        assert data["provider"] == "siliconflow"

    @pytest.mark.asyncio
    async def test_configure_model_set_default(self, async_client, sample_models, mock_model_manager):
        """Test configuring a model as default."""
        config_data = {
            "name": "New Default Model",
            "api_key": "sk-test-key",
            "base_url": "https://api.example.com/v1",
            "model_name": "new-model",
            "is_default": True,
        }

        response = await async_client.post("/api/v1/models/config", json=config_data)

        assert response.status_code == 201
        data = response.json()
        assert data["is_default"] is True

    @pytest.mark.asyncio
    async def test_configure_model_missing_required_fields(self, async_client):
        """Test configuring a model with missing required fields."""
        config_data = {
            "name": "Incomplete Model",
            # Missing api_key, base_url, model_name
        }

        response = await async_client.post("/api/v1/models/config", json=config_data)

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_configure_model_invalid_base_url(self, async_client):
        """Test configuring a model with invalid base_url."""
        config_data = {
            "name": "Invalid URL Model",
            "api_key": "sk-test-key",
            "base_url": "not-a-valid-url",
            "model_name": "test-model",
        }

        response = await async_client.post("/api/v1/models/config", json=config_data)

        # Should still accept (validation is lenient)
        assert response.status_code == 201
        data = response.json()
        assert data["provider"] == "custom"


class TestUpdateModelEndpoint:
    """Tests for PUT /api/v1/models/{model_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_model_success(self, async_client, sample_model, mock_model_manager):
        """Test updating an existing model configuration."""
        update_data = {
            "name": "Updated Model Name",
            "api_key": "new-encrypted-key",
            "base_url": "https://api.new-example.com/v1",
            "model_name": "updated-model",
            "is_default": True,
        }

        response = await async_client.put(
            f"/api/v1/models/{sample_model.id}", json=update_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == update_data["name"]
        assert data["base_url"] == update_data["base_url"]
        assert data["model_name"] == update_data["model_name"]
        assert data["is_default"] is True

        # Verify model manager was called
        mock_model_manager.register.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_model_provider_change(self, async_client, sample_model, mock_model_manager):
        """Test updating model with provider change."""
        update_data = {
            "name": sample_model.name,
            "api_key": "new-key",
            "base_url": "https://api.deepseek.com/v1",  # Changed to DeepSeek
            "model_name": "deepseek-chat",
            "is_default": False,
        }

        response = await async_client.put(
            f"/api/v1/models/{sample_model.id}", json=update_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "deepseek"  # Auto-detected

    @pytest.mark.asyncio
    async def test_update_model_not_found(self, async_client, mock_model_manager):
        """Test updating a non-existent model."""
        fake_id = uuid.uuid4()
        update_data = {
            "name": "Non-existent Model",
            "api_key": "key",
            "base_url": "https://api.example.com/v1",
            "model_name": "model",
        }

        response = await async_client.put(f"/api/v1/models/{fake_id}", json=update_data)

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_update_model_invalid_uuid(self, async_client):
        """Test updating with invalid UUID format."""
        update_data = {
            "name": "Test",
            "api_key": "key",
            "base_url": "https://api.example.com/v1",
            "model_name": "model",
        }

        response = await async_client.put("/api/v1/models/invalid-uuid", json=update_data)

        assert response.status_code == 422  # Validation error


class TestTestModelEndpoint:
    """Tests for POST /api/v1/models/{model_id}/test endpoint."""

    @pytest.mark.asyncio
    async def test_test_model_success(self, async_client, sample_model):
        """Test testing a model connection successfully."""
        with patch(
            "app.api.v1.endpoints.models.OpenAICompatibleProvider"
        ) as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.test_connection = MagicMock(return_value=True)
            mock_provider_class.return_value = mock_provider

            response = await async_client.post(f"/api/v1/models/{sample_model.id}/test")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "message" in data
            assert data["model_name"] == sample_model.model_name

    @pytest.mark.asyncio
    async def test_test_model_connection_failed(self, async_client, sample_model):
        """Test testing a model with failed connection."""
        with patch(
            "app.api.v1.endpoints.models.OpenAICompatibleProvider"
        ) as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.test_connection = MagicMock(return_value=False)
            mock_provider_class.return_value = mock_provider

            response = await async_client.post(f"/api/v1/models/{sample_model.id}/test")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "message" in data

    @pytest.mark.asyncio
    async def test_test_model_connection_error(self, async_client, sample_model):
        """Test testing a model with connection error."""
        with patch(
            "app.api.v1.endpoints.models.OpenAICompatibleProvider"
        ) as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.test_connection = MagicMock(
                side_effect=Exception("401 Unauthorized")
            )
            mock_provider_class.return_value = mock_provider

            response = await async_client.post(f"/api/v1/models/{sample_model.id}/test")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "API Key 无效" in data["message"] or "message" in data

    @pytest.mark.asyncio
    async def test_test_model_403_error(self, async_client, sample_model):
        """Test testing a model with 403 Forbidden error."""
        with patch(
            "app.api.v1.endpoints.models.OpenAICompatibleProvider"
        ) as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.test_connection = MagicMock(
                side_effect=Exception("403 Forbidden")
            )
            mock_provider_class.return_value = mock_provider

            response = await async_client.post(f"/api/v1/models/{sample_model.id}/test")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "权限不足" in data["message"] or "Forbidden" in data["message"]

    @pytest.mark.asyncio
    async def test_test_model_404_error(self, async_client, sample_model):
        """Test testing a model with 404 Not Found error."""
        with patch(
            "app.api.v1.endpoints.models.OpenAICompatibleProvider"
        ) as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.test_connection = MagicMock(
                side_effect=Exception("404 Not Found")
            )
            mock_provider_class.return_value = mock_provider

            response = await async_client.post(f"/api/v1/models/{sample_model.id}/test")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "不存在" in data["message"] or "Not Found" in data["message"]

    @pytest.mark.asyncio
    async def test_test_model_timeout_error(self, async_client, sample_model):
        """Test testing a model with timeout error."""
        with patch(
            "app.api.v1.endpoints.models.OpenAICompatibleProvider"
        ) as mock_provider_class:
            mock_provider = MagicMock()
            mock_provider.test_connection = MagicMock(
                side_effect=Exception("Connection timeout")
            )
            mock_provider_class.return_value = mock_provider

            response = await async_client.post(f"/api/v1/models/{sample_model.id}/test")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "超时" in data["message"] or "timeout" in data["message"].lower()

    @pytest.mark.asyncio
    async def test_test_model_not_found(self, async_client):
        """Test testing a non-existent model."""
        fake_id = uuid.uuid4()
        response = await async_client.post(f"/api/v1/models/{fake_id}/test")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_test_model_decryption_error(self, async_client, sample_model):
        """Test testing a model with API key decryption error."""
        with patch(
            "app.api.v1.endpoints.models.decrypt_api_key"
        ) as mock_decrypt:
            mock_decrypt.side_effect = Exception("Decryption failed")

            response = await async_client.post(f"/api/v1/models/{sample_model.id}/test")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "解密失败" in data["message"] or "decrypt" in data["message"].lower()


class TestGetModelEndpoint:
    """Tests for GET /api/v1/models/{model_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_model_success(self, async_client, sample_model):
        """Test getting a specific model configuration."""
        response = await async_client.get(f"/api/v1/models/{sample_model.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(sample_model.id)
        assert data["name"] == sample_model.name
        assert data["provider"] == sample_model.provider
        assert data["model_name"] == sample_model.model_name

        # Verify API key is not exposed
        assert "api_key" not in data
        assert "api_key_encrypted" not in data

    @pytest.mark.asyncio
    async def test_get_model_not_found(self, async_client):
        """Test getting a non-existent model."""
        fake_id = uuid.uuid4()
        response = await async_client.get(f"/api/v1/models/{fake_id}")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_get_model_invalid_uuid(self, async_client):
        """Test getting with invalid UUID format."""
        response = await async_client.get("/api/v1/models/invalid-uuid")

        assert response.status_code == 422  # Validation error


class TestDeleteModelEndpoint:
    """Tests for DELETE /api/v1/models/{model_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_model_success(self, async_client, sample_model, db_session):
        """Test deleting a model configuration."""
        response = await async_client.delete(f"/api/v1/models/{sample_model.id}")

        assert response.status_code == 204

        # Verify model is deleted
        from sqlalchemy import select

        result = await db_session.execute(
            select(ModelConfig).where(ModelConfig.id == sample_model.id)
        )
        assert result.scalar_one_or_none() is None

    @pytest.mark.asyncio
    async def test_delete_model_not_found(self, async_client):
        """Test deleting a non-existent model."""
        fake_id = uuid.uuid4()
        response = await async_client.delete(f"/api/v1/models/{fake_id}")

        assert response.status_code == 404


# =============================================================================
# Additional Edge Case Tests
# =============================================================================


class TestModelEdgeCases:
    """Edge case tests for model endpoints."""

    @pytest.mark.asyncio
    async def test_configure_model_with_unicode_name(self, async_client, mock_model_manager):
        """Test configuring a model with unicode characters in name."""
        config_data = {
            "name": "🤖 DeepSeek-V3（中文名）",
            "api_key": "sk-test-key",
            "base_url": "https://api.deepseek.com/v1",
            "model_name": "deepseek-chat",
        }

        response = await async_client.post("/api/v1/models/config", json=config_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == config_data["name"]

    @pytest.mark.asyncio
    async def test_configure_model_with_long_name(self, async_client, mock_model_manager):
        """Test configuring a model with a very long name."""
        config_data = {
            "name": "A" * 100,  # Very long name
            "api_key": "sk-test-key",
            "base_url": "https://api.example.com/v1",
            "model_name": "test-model",
        }

        response = await async_client.post("/api/v1/models/config", json=config_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "A" * 100

    @pytest.mark.asyncio
    async def test_concurrent_model_creation(self, async_client, mock_model_manager):
        """Test creating multiple models concurrently."""
        import asyncio

        async def create_model(i):
            config_data = {
                "name": f"并发模型 {i}",
                "api_key": f"sk-key-{i}",
                "base_url": f"https://api{i}.example.com/v1",
                "model_name": f"model-{i}",
            }
            return await async_client.post("/api/v1/models/config", json=config_data)

        # Create 5 models concurrently
        responses = await asyncio.gather(*[create_model(i) for i in range(5)])

        # All should succeed
        for response in responses:
            assert response.status_code == 201

        # Verify all models were created
        list_response = await async_client.get("/api/v1/models")
        data = list_response.json()
        assert len(data) == 5

    @pytest.mark.asyncio
    async def test_update_model_preserves_id(self, async_client, sample_model, mock_model_manager):
        """Test that updating a model preserves its ID."""
        original_id = sample_model.id

        update_data = {
            "name": "Updated Name",
            "api_key": "new-key",
            "base_url": "https://api.new.com/v1",
            "model_name": "new-model",
            "is_default": False,
        }

        response = await async_client.put(
            f"/api/v1/models/{sample_model.id}", json=update_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(original_id)

    @pytest.mark.asyncio
    async def test_multiple_default_models(self, async_client, sample_models, mock_model_manager):
        """Test behavior when setting multiple models as default."""
        # Create a new model as default
        config_data = {
            "name": "New Default",
            "api_key": "sk-key",
            "base_url": "https://api.example.com/v1",
            "model_name": "new-model",
            "is_default": True,
        }

        response = await async_client.post("/api/v1/models/config", json=config_data)
        assert response.status_code == 201

        # Check that the new model is default
        list_response = await async_client.get("/api/v1/models")
        data = list_response.json()

        default_models = [m for m in data if m["is_default"]]
        assert len(default_models) == 1
        assert default_models[0]["name"] == "New Default"
