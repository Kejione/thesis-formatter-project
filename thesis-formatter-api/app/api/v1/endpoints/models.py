"""
Model configuration API endpoints.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decrypt_api_key, encrypt_api_key
from app.models import ModelConfig
from app.schemas import ModelConfigCreate, ModelConfigResponse
from app.services.ai.provider import OpenAICompatibleProvider, get_model_manager

router = APIRouter(prefix="/models", tags=["models"])


def detect_provider(base_url: str) -> str:
    """Detect provider from base URL."""
    base_url_lower = base_url.lower()
    if "deepseek" in base_url_lower:
        return "deepseek"
    elif "openai" in base_url_lower:
        return "openai"
    elif "dashscope" in base_url_lower or "aliyun" in base_url_lower:
        return "qwen"
    elif "localhost" in base_url_lower or "127.0.0.1" in base_url_lower:
        return "ollama"
    elif "siliconflow" in base_url_lower:
        return "siliconflow"
    else:
        return "custom"


@router.get("", response_model=list[ModelConfigResponse])
async def list_models(
    provider: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    获取可用 AI 模型列表。

    可按 provider 筛选。
    """
    query = select(ModelConfig)
    if provider:
        query = query.where(ModelConfig.provider == provider)

    result = await db.execute(query.order_by(ModelConfig.priority, ModelConfig.created_at))
    models = result.scalars().all()

    return models


@router.post("/config", response_model=ModelConfigResponse, status_code=status.HTTP_201_CREATED)
async def configure_model(
    config: ModelConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    配置 AI 模型参数。

    - name: 显示名称
    - api_key: API Key（加密存储）
    - base_url: API 基础 URL
    - model_name: 模型标识
    - is_default: 是否设为默认模型
    """
    # Detect provider from base URL
    provider = detect_provider(config.base_url)

    # Encrypt API key
    encrypted_key = encrypt_api_key(config.api_key)

    # If setting as default, unset other defaults
    if config.is_default:
        result = await db.execute(select(ModelConfig).where(ModelConfig.is_default == True))
        existing_defaults = result.scalars().all()
        for model in existing_defaults:
            model.is_default = False

    # Get max priority
    result = await db.execute(
        select(ModelConfig.priority).order_by(ModelConfig.priority.desc()).limit(1)
    )
    max_priority = result.scalar() or 0

    model_config = ModelConfig(
        name=config.name,
        provider=provider,
        api_key_encrypted=encrypted_key,
        base_url=config.base_url,
        model_name=config.model_name,
        is_default=config.is_default,
        priority=max_priority + 1,
    )
    db.add(model_config)
    await db.commit()
    await db.refresh(model_config)

    # 将新配置注册到 ModelManager
    try:
        model_manager = get_model_manager()
        model_manager.register(
            provider_id=str(model_config.id),
            provider=OpenAICompatibleProvider(
                api_key=config.api_key,
                base_url=config.base_url,
                model_name=config.model_name,
                display_name=config.name,
            ),
            is_default=config.is_default,
            priority=max_priority + 1,
        )
        logger.info("新模型配置已注册到 ModelManager: {}", config.name)
    except Exception as exc:
        logger.warning("注册模型到 ModelManager 失败: {}", exc)

    return model_config


@router.get("/{model_id}", response_model=ModelConfigResponse)
async def get_model(
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取单个模型配置详情。
    """
    result = await db.execute(select(ModelConfig).where(ModelConfig.id == model_id))
    model = result.scalar_one_or_none()

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"模型配置 {model_id} 不存在",
        )

    return model


@router.put("/{model_id}", response_model=ModelConfigResponse)
async def update_model(
    model_id: UUID,
    config: ModelConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    更新模型配置。
    """
    result = await db.execute(select(ModelConfig).where(ModelConfig.id == model_id))
    model = result.scalar_one_or_none()

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"模型配置 {model_id} 不存在",
        )

    # If setting as default, unset other defaults
    if config.is_default:
        result = await db.execute(
            select(ModelConfig).where(ModelConfig.is_default == True, ModelConfig.id != model_id)
        )
        existing_defaults = result.scalars().all()
        for m in existing_defaults:
            m.is_default = False

    model.name = config.name
    model.api_key_encrypted = encrypt_api_key(config.api_key)
    model.base_url = config.base_url
    model.model_name = config.model_name
    model.is_default = config.is_default
    model.provider = detect_provider(config.base_url)

    await db.commit()
    await db.refresh(model)

    # 更新 ModelManager 中的注册信息
    try:
        model_manager = get_model_manager()
        model_manager.register(
            provider_id=str(model.id),
            provider=OpenAICompatibleProvider(
                api_key=config.api_key,
                base_url=config.base_url,
                model_name=config.model_name,
                display_name=config.name,
            ),
            is_default=config.is_default,
            priority=model.priority,
        )
        logger.info("模型配置已更新到 ModelManager: {}", config.name)
    except Exception as exc:
        logger.warning("更新 ModelManager 注册失败: {}", exc)

    return model


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    删除模型配置。
    """
    result = await db.execute(select(ModelConfig).where(ModelConfig.id == model_id))
    model = result.scalar_one_or_none()

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"模型配置 {model_id} 不存在",
        )

    await db.delete(model)
    await db.commit()


@router.post("/{model_id}/test")
async def test_model(
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    测试模型连接。

    解密 API Key，创建 OpenAI 兼容客户端，发送一个简单的请求
    验证 API Key 和连接是否正常。返回真实的成功/失败结果。
    """
    result = await db.execute(select(ModelConfig).where(ModelConfig.id == model_id))
    model = result.scalar_one_or_none()

    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"模型配置 {model_id} 不存在",
        )

    # 解密 API Key
    try:
        api_key = decrypt_api_key(model.api_key_encrypted)
    except Exception as exc:
        logger.error("解密 API Key 失败 model_id={}: {}", model_id, exc)
        return {
            "success": False,
            "message": f"API Key 解密失败: {str(exc)}",
            "model_name": model.model_name,
        }

    if not api_key:
        return {
            "success": False,
            "message": "API Key 为空，请先配置有效的 API Key",
            "model_name": model.model_name,
        }

    # 创建 provider 并测试连接
    provider = OpenAICompatibleProvider(
        api_key=api_key,
        base_url=model.base_url,
        model_name=model.model_name,
        display_name=model.name,
    )

    try:
        is_ok = await provider.test_connection()
        if is_ok:
            logger.info("模型连接测试成功: model_id={} name={}", model_id, model.name)
            return {
                "success": True,
                "message": f"模型 [{model.name}] 连接测试成功",
                "model_name": model.model_name,
                "provider": model.provider,
                "base_url": model.base_url,
            }
        else:
            logger.warning("模型连接测试返回空响应: model_id={}", model_id)
            return {
                "success": False,
                "message": f"模型 [{model.name}] 返回空响应，请检查模型名称和 API Key",
                "model_name": model.model_name,
            }
    except Exception as exc:
        error_msg = str(exc)
        logger.error("模型连接测试失败 model_id={}: {}", model_id, error_msg)

        # 对常见错误提供更友好的提示
        friendly_msg = error_msg
        if "401" in error_msg or "Unauthorized" in error_msg:
            friendly_msg = "API Key 无效或已过期，请检查配置"
        elif "403" in error_msg or "Forbidden" in error_msg:
            friendly_msg = "API Key 权限不足，请检查账户权限"
        elif "404" in error_msg:
            friendly_msg = f"模型名称 [{model.model_name}] 不存在，请检查模型标识"
        elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            friendly_msg = "连接超时，请检查 base_url 是否正确以及网络是否可达"
        elif "Connection" in error_msg:
            friendly_msg = f"无法连接到 {model.base_url}，请检查服务地址是否正确"

        return {
            "success": False,
            "message": f"模型 [{model.name}] 连接测试失败: {friendly_msg}",
            "model_name": model.model_name,
            "error_detail": error_msg,
        }
