"""Run the FastAPI application using Uvicorn."""

import argparse
import warnings
import uvicorn


# Suppress specific warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic._internal._fields")

# Start the Uvicorn server
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run FastAPI application")
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to run the server on (default: 8000)"
    )
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload on code changes")
    args = parser.parse_args()

    uvicorn.run("src.main:app", host="127.0.0.1", port=args.port, reload=args.reload)
