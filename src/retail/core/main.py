"""Main FastAPI application."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from retail.api.v1 import auth
from retail.core.dependencies import (
    get_settings,
    get_square_api_url,
    get_square_base_url,
    get_square_client,
)
from retail.core.settings import Provider, SquareSettings
from retail.plugins.square import create_square_router

app = FastAPI(
    title="Retail API",
    description="API for retail integrations",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Add your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
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
async def root():
    """Root endpoint."""
    return {"message": "Welcome to the Retail API"}
