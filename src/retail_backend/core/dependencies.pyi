"""
FastAPI dependencies for the retail application.
"""

from functools import lru_cache
from typing import Union

from square.client import Client

from .settings import Provider, ShopifySettings, SquareSettings

@lru_cache()
def get_settings(provider: Provider) -> Union[ShopifySettings, SquareSettings]: ...
@lru_cache()
def get_square_client() -> Client: ...
@lru_cache()
def get_square_base_url() -> str: ...
@lru_cache()
def get_square_api_url() -> str: ...
