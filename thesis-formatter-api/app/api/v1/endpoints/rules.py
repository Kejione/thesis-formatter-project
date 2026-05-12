"""
Rule API endpoints.
"""

import uuid
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Rule
from app.schemas import RuleCreate, RuleResponse
from app.services.storage import get_storage_service
from app.tasks.format_tasks import parse_spec_file

router = APIRouter(prefix="/rules", tags=["rules"])


@router.post("/parse")
async def parse_rule_file(
    spec_file: UploadFile = File(..., description="学校格式规范文件"),
    model_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    AI 解析格式规范文件。

    将上传的规范文件（PDF/DOCX/TXT）上传到 MinIO，然后触发 Celery 任务
    进行 AI 解析，返回结构化的格式规则 JSON。

    MVP 模式下直接同步解析并返回结果。
    """
    if not spec_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="必须提供规范文件",
        )

    storage = get_storage_service()

    # 确保存储桶存在
    try:
        storage.ensure_bucket()
    except Exception as exc:
        logger.error("确保存储桶存在失败: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="文件存储服务不可用，请稍后重试",
        ) from exc

    # 上传规范文件到 MinIO
    spec_file_data = await spec_file.read()
    spec_file_key = f"spec/{uuid.uuid4().hex}_{spec_file.filename}"

    # 根据文件扩展名确定 content_type
    content_type = "application/octet-stream"
    fname_lower = spec_file.filename.lower()
    if fname_lower.endswith(".pdf"):
        content_type = "application/pdf"
    elif fname_lower.endswith(".docx"):
        content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif fname_lower.endswith(".txt"):
        content_type = "text/plain"

    try:
        storage.upload_file(
            file_data=spec_file_data,
            object_key=spec_file_key,
            content_type=content_type,
        )
        logger.info("规范文件已上传: key={} size={}", spec_file_key, len(spec_file_data))
    except ConnectionError as exc:
        logger.error("规范文件上传失败: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="规范文件上传失败，存储服务连接异常",
        ) from exc

    # MVP 模式：直接同步调用解析逻辑
    # 生产环境可改为触发 Celery 异步任务: parse_spec_file.delay(task_id, spec_file_key, model_id)
    try:
        import asyncio
        import tempfile
        import os

        from app.services.rule import get_rule_engine
        from app.services.ai import SpecParser
        from app.services.ai.provider import get_model_manager

        # 下载到临时文件
        file_bytes = storage.download_file(spec_file_key)
        suffix = os.path.splitext(spec_file.filename)[1].lower() or ".bin"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(file_bytes)
        tmp.close()

        try:
            # 提取文本
            ext = suffix
            if ext == ".txt":
                with open(tmp.name, "r", encoding="utf-8") as f:
                    text = f.read()
            elif ext == ".pdf":
                import pdfplumber
                pages_text = []
                with pdfplumber.open(tmp.name) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            pages_text.append(page_text)
                text = "\n\n".join(pages_text)
            elif ext == ".docx":
                from docx import Document as DocxDocument
                doc = DocxDocument(tmp.name)
                text = "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
            else:
                raise ValueError(f"不支持的规范文件格式: {ext}")

            if not text.strip():
                raise ValueError("规范文件内容为空，无法解析")

            # 调用 AI 解析
            model_manager = get_model_manager()
            parser = SpecParser(model_manager)
            rules = await parser.parse(text=text, model_id=model_id)

            # 校验规则
            rule_engine = get_rule_engine()
            validation_errors = rule_engine.validate_rules(rules)

            # 保存规则到数据库
            school_name = rules.get("school_name", "未知学校")
            rule_record = Rule(
                name=f"AI 解析规则 - {school_name}",
                source="ai_parsed",
                rule_data=rules,
                school_name=school_name,
                is_active=True,
            )
            db.add(rule_record)
            await db.commit()
            await db.refresh(rule_record)

            logger.info(
                "规范文件解析完成: rule_id={} school={}",
                rule_record.id,
                school_name,
            )

            return {
                "message": "规范解析成功",
                "file_name": spec_file.filename,
                "model_id": model_id,
                "rule_id": str(rule_record.id),
                "rules": rules,
                "validation_warnings": validation_errors if validation_errors else None,
            }

        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    except ValueError as exc:
        logger.warning("规范文件解析失败（业务逻辑错误）: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except ConnectionError as exc:
        logger.error("规范文件下载失败: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="文件下载失败，存储服务连接异常",
        ) from exc
    except Exception as exc:
        logger.error("规范文件解析失败（未知错误）: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"规范文件解析失败: {str(exc)}",
        ) from exc


@router.get("", response_model=list[RuleResponse])
async def list_rules(
    school_name: Optional[str] = None,
    is_active: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """
    获取格式规则列表。

    可按学校名称筛选，默认只返回启用的规则。
    """
    query = select(Rule).where(Rule.is_active == is_active)
    if school_name:
        query = query.where(Rule.school_name.ilike(f"%{school_name}%"))

    result = await db.execute(query.order_by(Rule.created_at.desc()))
    rules = result.scalars().all()

    return rules


@router.get("/{rule_id}", response_model=RuleResponse)
async def get_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取单个格式规则详情。
    """
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"规则 {rule_id} 不存在",
        )

    return rule


@router.post("", response_model=RuleResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    rule_data: RuleCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    创建格式规则。

    手动创建格式规则，或保存 AI 解析结果。
    """
    rule = Rule(
        name=rule_data.name,
        source=rule_data.source,
        rule_data=rule_data.rule_data.model_dump(exclude_none=True),
        school_name=rule_data.school_name,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    return rule


@router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: UUID,
    rule_data: RuleCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    更新格式规则。
    """
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"规则 {rule_id} 不存在",
        )

    rule.name = rule_data.name
    rule.rule_data = rule_data.rule_data.model_dump(exclude_none=True)
    rule.school_name = rule_data.school_name

    await db.commit()
    await db.refresh(rule)

    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    删除格式规则。
    """
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()

    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"规则 {rule_id} 不存在",
        )

    await db.delete(rule)
    await db.commit()
