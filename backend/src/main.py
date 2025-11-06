"""
FastAPI application entry point and configuration.

This module sets up the FastAPI application with all necessary middleware,
database configuration, routing, and static file serving for the dish
healthiness analysis application.
"""

import logging

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
        format=(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ),
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('app.log', encoding='utf-8')
        ]
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
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url="/api-docs"
    )

    # Add session middleware for cookie-based authentication
    app.add_middleware(
        SessionMiddleware,
        secret_key="your-secret-key-change-in-production"
    )

    # Add CORS middleware for React frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:2512"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount static files directory for serving images
    app.mount("/images", StaticFiles(directory=str(IMAGE_DIR)), name="images")
    logger.info(f"Mounted static files at /images -> {IMAGE_DIR}")

    # Include API router
    app.include_router(api_router)
    logger.info("API router included")

    logger.info("Application initialization complete")
    return app


# Create the FastAPI app instance
app = create_app()


@app.get("/")
async def root():
    """
    Root endpoint.

    Returns:
        dict: Welcome message
    """
    return {
        "message": "Dish Healthiness API",
        "docs": "/api-docs"
    }


@app.get("/health")
async def health():
    """
    Health check endpoint.

    Returns:
        dict: Health status
    """
    return {"status": "healthy"}

