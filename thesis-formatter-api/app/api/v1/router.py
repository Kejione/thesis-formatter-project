"""
API v1 router combining all endpoints.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import models, rules, tasks, templates

api_router = APIRouter()

api_router.include_router(tasks.router)
api_router.include_router(rules.router)
api_router.include_router(models.router)
api_router.include_router(templates.router)
