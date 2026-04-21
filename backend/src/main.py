"""
FastAPI application entry point and configuration.

This module sets up the FastAPI application with all necessary middleware,
database configuration, routing, and static file serving for the dish
healthiness analysis application.
"""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from src import models
from src.api.api_router import api_router
from src.configs import IMAGE_DIR, settings
from src.database import engine


def configure_logging():
    """
    Configure application logging.

    Sets up both console and file logging with appropriate formatting
    for debugging and monitoring purposes.
    """
    logging.basicConfig(
        level=logging.INFO,
        format=("%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
        handlers=[logging.StreamHandler(), logging.FileHandler("app.log", encoding="utf-8")],
    )


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        FastAPI: Configured FastAPI application instance
    """
    # Load environment variables from .env file
    load_dotenv()

    # Configure logging
    configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("Initializing Dish Healthiness application...")

    # Create database tables
    models.Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")

    # Create FastAPI app
    fastapi_app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url="/api-docs",
    )

    # Add session middleware for cookie-based authentication
    fastapi_app.add_middleware(
        SessionMiddleware, secret_key="your-secret-key-change-in-production"
    )

    # Configure CORS origins from environment variable
    allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:2512")

    # If ALLOWED_ORIGINS is "*", allow all origins
    # Note: When using "*", allow_credentials must be False
    if allowed_origins_env == "*":
        allowed_origins = ["*"]
        allow_credentials = False
    else:
        # Split by comma and strip whitespace, or use as single origin
        allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",")]
        # Always include localhost for development
        if "http://localhost:2512" not in allowed_origins:
            allowed_origins.append("http://localhost:2512")
        allow_credentials = True

    logger.info("CORS allowed origins: %s", allowed_origins)
    logger.info("CORS allow credentials: %s", allow_credentials)

    # Add CORS middleware for React frontend
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static files directory for serving images
    fastapi_app.mount("/images", StaticFiles(directory=str(IMAGE_DIR)), name="images")
    logger.info("Mounted static files at /images -> %s", IMAGE_DIR)

    # Include API router
    fastapi_app.include_router(api_router)
    logger.info("API router included")

    logger.info("Application initialization complete")
    return fastapi_app


# Create the FastAPI app instance
app = create_app()


@app.get("/")
async def root():
    """
    Root endpoint.

    Returns:
        dict: Welcome message
    """
    return {"message": "Dish Healthiness API", "docs": "/api-docs"}


@app.get("/health")
async def health():
    """
    Health check endpoint.

    Returns:
        dict: Health status
    """
    return {"status": "healthy"}
