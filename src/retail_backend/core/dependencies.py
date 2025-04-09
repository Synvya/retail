"""
FastAPI dependencies for the retail application.
"""

from functools import lru_cache
from typing import Union

from square.client import Client
from square.http.auth.o_auth_2 import BearerAuthCredentials

from .settings import Provider, ShopifySettings, SquareSettings


@lru_cache()
def get_settings(provider: Provider) -> Union[ShopifySettings, SquareSettings]:
    """
    Get the settings for the retail application.
    """
    if provider == Provider.SHOPIFY:
        return ShopifySettings(
            api_key="", api_secret="", access_token=""
        )  # Reads Shopify-related vars from .env
    elif provider == Provider.SQUARE:
        return SquareSettings()  # Reads Square-related vars from .env
    else:
        raise ValueError(f"Invalid provider: {provider}")


@lru_cache()
def get_square_client() -> Client:
    """
    Injection method to get the Square client.
    """
    settings = get_settings(Provider.SQUARE)
    if not isinstance(settings, SquareSettings):
        raise ValueError("Settings are not of type SquareSettings")

    client = Client(
        bearer_auth_credentials=BearerAuthCredentials(access_token=settings.access_token),
        environment=settings.environment,
    )
    return client


@lru_cache()
def get_square_base_url() -> str:
    """
    Returns the Square API base URL depending on the environment.
    """
    settings = get_settings(Provider.SQUARE)
    if not isinstance(settings, SquareSettings):
        raise ValueError("Settings are not of type SquareSettings")

    base_urls = {
        "sandbox": "https://connect.squareupsandbox.com",
        "production": "https://connect.squareup.com",
    }

    try:
        return base_urls[settings.environment]
    except KeyError:
        raise ValueError(f"Invalid environment: {settings.environment}")


@lru_cache()
def get_square_api_url() -> str:
    """
    Returns the Square API URL depending on the environment.
    """
    return f"{get_square_base_url()}/v2"
