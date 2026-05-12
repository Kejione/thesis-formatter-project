"""
Template API endpoints.
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import Rule, Template
from app.schemas import TemplateResponse

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("", response_model=list[TemplateResponse])
async def list_templates(
    school_name: Optional[str] = None,
    thesis_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    获取预置学校模板列表。

    可按学校名称和论文类型筛选。
    """
    query = select(Template)
    if school_name:
        query = query.where(Template.school_name.ilike(f"%{school_name}%"))
    if thesis_type:
        query = query.where(Template.thesis_type == thesis_type)

    result = await db.execute(query.order_by(Template.usage_count.desc(), Template.created_at.desc()))
    templates = result.scalars().all()

    return templates


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取单个模板详情。
    """
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"模板 {template_id} 不存在",
        )

    return template


@router.get("/{template_id}/rules")
async def get_template_rules(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    获取模板关联的格式规则。
    """
    result = await db.execute(select(Template).where(Template.id == template_id))
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"模板 {template_id} 不存在",
        )

    rule_result = await db.execute(select(Rule).where(Rule.id == template.rule_id))
    rule = rule_result.scalar_one_or_none()

    return rule
