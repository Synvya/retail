"""Main module."""

from fastapi import FastAPI

from retail.core.settings import Provider

app: FastAPI

async def root() -> dict:
    """Root endpoint."""

payment_provider: str
settings: Provider
