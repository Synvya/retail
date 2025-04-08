"""Main module."""

from fastapi import FastAPI

from retail_backend.core.settings import Provider

app: FastAPI

async def root() -> dict:
    """Root endpoint."""

payment_provider: str
settings: Provider
