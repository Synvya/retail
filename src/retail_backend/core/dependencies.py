"""
FastAPI dependencies for the retail application.
"""

import logging
from functools import lru_cache
from typing import Union

from square.client import Client
from square.http.auth.o_auth_2 import BearerAuthCredentials

from .settings import Provider, ShopifySettings, SquareSettings

# Setup logger
logger = logging.getLogger("dependencies")


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
        settings = SquareSettings()  # Reads Square-related vars from .env
        logger.info(
            "get_settings returning SquareSettings with environment: %s", settings.environment
        )
        return settings
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

    logger.info("Creating Square client with environment: %s", settings.environment)

    client = Client(
        bearer_auth_credentials=BearerAuthCredentials(access_token=settings.developer_access_token),
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
        url = base_urls[settings.environment]
        logger.info("Using Square API base URL for environment %s: %s", settings.environment, url)
        return url
    except KeyError as e:
        raise ValueError(f"Invalid environment: {settings.environment}") from e


@lru_cache()
def get_square_api_url() -> str:
    """
    Returns the Square API URL depending on the environment.
    """
    return f"{get_square_base_url()}/v2"
