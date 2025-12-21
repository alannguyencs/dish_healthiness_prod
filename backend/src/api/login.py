"""
API routes and handlers for user login functionality.

This module provides JSON-based login functionality for authentication
with session management.
"""

import logging
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.auth import authenticate_user, create_access_token

# Setup logger
logger = logging.getLogger(__name__)

# Create router for login endpoints
router = APIRouter(prefix="/api/login", tags=["login"])


class LoginRequest(BaseModel):
    """Login request model."""

    username: str
    password: str


@router.post("/")
async def process_login(login_data: LoginRequest) -> JSONResponse:
    """
    Handle POST request for user login.

    This endpoint processes login requests, authenticates users,
    and creates session cookies for successful logins.

    Args:
        login_data (LoginRequest): Login credentials

    Returns:
        JSONResponse: JSON response with auth status and user data
    """
    logger.info("Login attempt for username: %s", login_data.username)

    # Authenticate user
    user = authenticate_user(login_data.username, login_data.password)

    if not user:
        logger.error("Authentication failed for: %s", login_data.username)
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"success": False, "message": "Invalid username or password"},
        )

    logger.info("Authentication successful for: %s (ID: %s)", user.username, user.id)

    # Create access token
    access_token = create_access_token(data={"username": login_data.username})

    # Create response with user data
    response = JSONResponse(
        content={
            "success": True,
            "message": "Login successful",
            "user": {"id": user.id, "username": user.username},
        }
    )
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=7776000,  # 90 days
        path="/",
    )

    return response


@router.post("/logout")
async def logout() -> JSONResponse:
    """
    Handle user logout.

    Returns:
        JSONResponse: JSON response confirming logout
    """
    response = JSONResponse(content={"success": True, "message": "Logout successful"})
    response.delete_cookie(key="access_token")
    return response
