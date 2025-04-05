"""
FastAPI dependencies for the retail application.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings
from square.client import Client  # type: ignore

from .settings import Provider

@lru_cache()
def get_settings(provider: Provider) -> BaseSettings: ...
@lru_cache()
def get_square_client() -> Client: ...
@lru_cache()
def get_square_base_url() -> str: ...
@lru_cache()
def get_square_api_url() -> str: ...
