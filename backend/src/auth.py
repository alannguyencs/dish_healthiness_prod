"""
Authentication utilities for JWT token generation and user verification.

This module provides functions for user authentication, JWT token creation
and validation, and session management for the food healthiness application.
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Union

from fastapi import Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from src.crud.crud_user import get_user_by_username
from src.models import Users

# OAuth2PasswordBearer instance for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# JWT configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"

# Password hashing context
bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def authenticate_user(username: str, password: str) -> Union[Users, bool]:
    """
    Authenticate user with provided username and password.

    Args:
        username (str): The username to authenticate
        password (str): The password to authenticate

    Returns:
        Union[Users, bool]: User object if authentication successful,
                           False otherwise
    """
    user = get_user_by_username(username)
    if not user:
        return False

    if not bcrypt_context.verify(password, user.hashed_password):
        return False

    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data (dict): The data to encode in the token
        expires_delta (Optional[timedelta]): Optional expiration time delta

    Returns:
        str: The encoded JWT token
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=90)

    to_encode.update({"expire": expire.isoformat()})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def get_current_user_from_token(token: str) -> Optional[Users]:
    """
    Validate JWT token and return the corresponding user.

    Args:
        token (str): JWT token to decode

    Returns:
        Optional[Users]: User object if token is valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("username")

        if username is None:
            return None

        # Username is unique, get user from database
        user = get_user_by_username(username)
        return user

    except JWTError:
        return None


def authenticate_user_from_request(request: Request) -> Union[Users, bool]:
    """
    Authenticate user from HTTP request using session cookie.

    Args:
        request (Request): FastAPI request object

    Returns:
        Union[Users, bool]: User object if authenticated, False otherwise
    """
    token = request.cookies.get("access_token")
    if not token:
        return False

    user = get_current_user_from_token(token)
    if not user:
        return False

    return user
