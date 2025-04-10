"""Main FastAPI application."""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from retail_backend.api.v1 import auth
from retail_backend.core.database import Base, engine
from retail_backend.core.dependencies import (
    get_settings,
    get_square_api_url,
    get_square_base_url,
    get_square_client,
)
from retail_backend.core.settings import Provider, SquareSettings
from retail_backend.plugins.square import create_square_router

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")


# Request tracing middleware
class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Request tracing middleware."""

    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        # Log the incoming request
        logger.info(f"Request: {request.method} {request.url}")
        logger.info(f"Headers: {dict(request.headers)}")

        # Process the request
        response = await call_next(request)

        # Log the response
        logger.info(f"Response status: {response.status_code}")
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan for the FastAPI application."""
    print("Initializing database...")
    Base.metadata.create_all(bind=engine)
    print("Database initialized successfully!")
    yield
    # Cleanup actions go here (if needed)


app = FastAPI(
    title="Retail API",
    description="API for retail integrations",
    version="1.0.0",
)

# Add request tracing middleware
app.add_middleware(RequestTracingMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_origin_regex=r"https://.*\.lovableproject\.com",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

payment_provider = os.getenv("PAYMENT_PROVIDER", "square")


if payment_provider == "square":
    # Resolve the values at startup
    settings = get_settings(Provider.SQUARE)
    if not isinstance(settings, SquareSettings):
        raise ValueError("Settings are not of type SquareSettings")
    client = get_square_client()
    square_base_url = get_square_base_url()
    square_api_url = get_square_api_url()
    app.include_router(
        create_square_router(client, settings, square_base_url, square_api_url),
        prefix="/square",
    )
# elif payment_provider == "shopify":
#     app.include_router(create_shopify_router(settings), prefix="/shopify")

# Include routers
app.include_router(auth.router, prefix="/api/v1")


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {"message": "Welcome to the Retail API"}


@app.middleware("http")
async def log_raw_request(request: Request, call_next: Callable) -> Any:
    body = await request.body()
    logger.info(f"Raw request body: {body!r}")
    response = await call_next(request)
    return response
