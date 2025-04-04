"""Main module."""

from fastapi import FastAPI

app: FastAPI

async def root() -> dict:
    """Root endpoint."""
