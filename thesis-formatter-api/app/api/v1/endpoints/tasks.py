"""
Task API endpoints.
"""

import uuid
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Change, Task
from app.schemas import ChangeRecord, ChangeLogResponse, TaskStatus
from app.services.storage import get_storage_service
from app.services.ai.provider import get_model_manager
from app.tasks.format_tasks import process_format_check, process_format_fix

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _load_model_configs_on_startup() -> None:
    """从数据库加载模型配置到 ModelManager（启动时调用）。

    此函数应在应用启动事件中调用一次，将数据库中已配置的
    AI 模型注册到全局 ModelManager 单例中。
    """
    import asyncio

    from app.core.database import get_db_context
    from app.core.security import decrypt_api_key
    from app.models import ModelConfig

    model_manager = get_model_manager()

    async def _load():
        async with get_db_context() as db:
            result = await db.execute(
                select(ModelConfig).where(ModelConfig.is_active == True)  # noqa: E712
            )
            configs = result.scalars().all()
            for cfg in configs:
                try:
                    api_key = decrypt_api_key(cfg.api_key_encrypted)
                    model_manager.register_from_config({
                        "name": cfg.name,
                        "api_key_decrypted": api_key,
                        "base_url": cfg.base_url,
                        "model_name": cfg.model_name,
                        "is_default": cfg.is_default,
                        "priority": cfg.priority,
                    })
                except Exception as exc:
                    logger.warning("加载模型配置失败 [{}]: {}", cfg.name, exc)

    try:
        asyncio.run(_load())
    except RuntimeError:
        # 如果已经在事件循环中运行，使用 nest_asyncio 或跳过
        logger.warning("无法在启动时加载模型配置，将在首次使用时延迟加载")


@router.post("", response_model=TaskStatus, status_code=status.HTTP_201_CREATED)
async def create_task(
    thesis_file: UploadFile = File(..., description="毕业论文 .docx 文件"),
    spec_file: Optional[UploadFile] = File(None, description="学校格式规范文件"),
    template_id: Optional[UUID] = Form(None, description="预置学校模板 ID"),
    model_id: Optional[str] = Form(None, description="AI 模型 ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    创建格式检查任务。

    - 上传毕业论文 .docx 文件（必填）
    - 上传学校格式规范文件（可选，与 template_id 二选一）
    - 指定预置模板 ID（可选）
    - 指定 AI 模型 ID（可选，使用默认配置）
    """
    # Validate file extension
    if not thesis_file.filename or not thesis_file.filename.endswith(".docx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="论文文件必须是 .docx 格式",
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

    # 上传论文文件到 MinIO
    thesis_file_data = await thesis_file.read()
    thesis_file_key = f"thesis/{uuid.uuid4().hex}_{thesis_file.filename}"
    try:
        storage.upload_file(
            file_data=thesis_file_data,
            object_key=thesis_file_key,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        logger.info("论文文件已上传: key={} size={}", thesis_file_key, len(thesis_file_data))
    except ConnectionError as exc:
        logger.error("论文文件上传失败: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="文件上传失败，存储服务连接异常",
        ) from exc

    # 上传规范文件到 MinIO（如果提供）
    spec_file_key = None
    if spec_file:
        spec_file_data = await spec_file.read()
        spec_file_key = f"spec/{uuid.uuid4().hex}_{spec_file.filename}"
        try:
            content_type = "application/octet-stream"
            if spec_file.filename:
                fname_lower = spec_file.filename.lower()
                if fname_lower.endswith(".pdf"):
                    content_type = "application/pdf"
                elif fname_lower.endswith(".docx"):
                    content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                elif fname_lower.endswith(".txt"):
                    content_type = "text/plain"
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

    # Create task record
    task = Task(
        status="pending",
        thesis_file_key=thesis_file_key,
        spec_file_key=spec_file_key,
        template_id=template_id,
        model_id=model_id,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    # 触发 Celery 异步任务执行格式检查
    try:
        process_format_check.delay(str(task.id))
        logger.info("格式检查 Celery 任务已触发: task_id={}", task.id)
    except Exception as exc:
        logger.error("触发 Celery 任务失败: {}", exc)
        # 任务已创建，仅记录日志，不回滚数据库记录
        # Celery 可能暂时不可用，后续可通过重试机制处理

    return TaskStatus(
        id=task.id,
        status=task.status,
        created_at=task.created_at,
    )


@router.get("/{task_id}", response_model=TaskStatus)
async def get_task_status(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取任务状态。

    返回任务当前状态、问题数量、是否可修复等信息。
    """
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务 {task_id} 不存在",
        )

    return TaskStatus(
        id=task.id,
        status=task.status,
        created_at=task.created_at,
        updated_at=task.updated_at,
        issue_count=len(task.issues) if task.issues else 0,
        fix_available=task.status == "completed" and len(task.issues or []) > 0,
        error_message=task.error_message,
    )


@router.get("/{task_id}/report")
async def get_task_report(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取格式检查报告。

    返回完整的格式检查报告，包括：
    - 总览（通过/警告/错误数量）
    - 问题列表（按严重程度分类）
    - 使用的规则列表
    - 论文元信息
    """
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务 {task_id} 不存在",
        )

    if task.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"任务状态为 {task.status}，尚未完成检查",
        )

    # 构建完整报告
    issues_data = []
    if task.issues:
        for issue in task.issues:
            issues_data.append({
                "id": str(issue.id),
                "severity": issue.severity,
                "category": issue.category,
                "location": issue.location,
                "rule_id": issue.rule_id,
                "current_value": issue.current_value,
                "expected_value": issue.expected_value,
                "suggestion": issue.suggestion,
                "is_fixed": issue.is_fixed,
            })

    rules_applied = []
    if task.rule_snapshot:
        rules_applied = [
            {"key": k, "value": v}
            for k, v in task.rule_snapshot.items()
            if v is not None
        ]

    return {
        "task_id": task.id,
        "summary": task.result_summary or {},
        "issues": issues_data,
        "rules_applied": rules_applied,
        "metadata": {},
    }


@router.post("/{task_id}/fix")
async def fix_task(
    task_id: UUID,
    issue_ids: Optional[list[UUID]] = None,  # If None, fix all issues
    db: AsyncSession = Depends(get_db),
):
    """
    执行格式修复。

    - 如果不提供 issue_ids，修复所有问题
    - 如果提供 issue_ids，仅修复指定问题
    """
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务 {task_id} 不存在",
        )

    if task.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"任务状态为 {task.status}，无法执行修复",
        )

    # 更新任务状态为 fixing
    task.status = "fixing"
    await db.commit()

    # 触发 Celery 异步任务执行格式修复
    issue_ids_str = [str(iid) for iid in issue_ids] if issue_ids else None
    try:
        process_format_fix.delay(str(task_id), issue_ids=issue_ids_str)
        logger.info("格式修复 Celery 任务已触发: task_id={}", task_id)
    except Exception as exc:
        logger.error("触发修复 Celery 任务失败: {}", exc)
        # 回滚任务状态
        task.status = "completed"
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="任务调度服务不可用，请稍后重试",
        ) from exc

    return {"message": "修复任务已启动", "task_id": task_id}


@router.get("/{task_id}/download")
async def download_fixed_document(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    下载修复后的文档。

    返回修复后的 .docx 文件的预签名下载 URL。
    """
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务 {task_id} 不存在",
        )

    if not task.fixed_file_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="修复文档尚未生成",
        )

    # 使用 StorageService 生成预签名 URL
    storage = get_storage_service()
    try:
        download_url = storage.get_presigned_url(task.fixed_file_key, expires_hours=1)
        logger.info("已生成下载预签名 URL: task_id={} key={}", task_id, task.fixed_file_key)
    except (ConnectionError, FileNotFoundError) as exc:
        logger.error("生成预签名 URL 失败: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="无法生成下载链接，文件服务异常",
        ) from exc

    # 从 file_key 中提取原始文件名
    file_name = task.fixed_file_key.split("/")[-1] if "/" in task.fixed_file_key else "fixed_document.docx"

    return {
        "download_url": download_url,
        "file_name": file_name,
    }


@router.get("/{task_id}/changelog", response_model=ChangeLogResponse)
async def get_changelog(
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取修改记录。

    返回所有格式修改的详细记录，从数据库 Change 表中查询。
    """
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务 {task_id} 不存在",
        )

    # 从数据库查询 Change 记录
    changes_result = await db.execute(
        select(Change)
        .where(Change.task_id == task_id)
        .order_by(Change.created_at.asc())
    )
    changes = changes_result.scalars().all()

    change_records = [
        ChangeRecord(
            id=change.id,
            category=change.category,
            location=change.location,
            before_value=change.before_value,
            after_value=change.after_value,
            risk_level=change.risk_level,
            created_at=change.created_at,
        )
        for change in changes
    ]

    return ChangeLogResponse(
        task_id=task.id,
        total_changes=len(change_records),
        changes=change_records,
    )
