"""
API router configuration.

This module aggregates all API endpoints into a single router
for the FastAPI application.
"""

from fastapi import APIRouter

from src.api import login, dashboard, date, item

# Create main API router
api_router = APIRouter()

# Include all sub-routers
api_router.include_router(login.router)
api_router.include_router(dashboard.router)
api_router.include_router(date.router)
api_router.include_router(item.router)
