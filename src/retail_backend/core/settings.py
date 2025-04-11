"""
Settings for the retail application.
"""

import os
from enum import Enum

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

SQUARE_VERSION = "2025-03-19"
SQUARE_BASE_URL_SANDBOX = "https://connect.squareupsandbox.com"
SQUARE_BASE_URL_PRODUCTION = "https://connect.squareup.com"

load_dotenv()


SQUARE_OAUTH_REDIRECT_URI = os.getenv(
    "SQUARE_REDIRECT_URI", "http://localhost:8000/square/oauth/callback"
)


class Provider(Enum):
    """
    Provider for the retail application.
    """

    SQUARE = "SQUARE"
    SHOPIFY = "SHOPIFY"


class SquareSettings(BaseSettings):
    """
    Settings for the Square API.
    """

    square_app_id: str = ""
    square_app_secret: str = ""
    environment: str = "sandbox"
    developer_access_token: str = ""
    square_redirect_uri: str = ""
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # env_prefix="SQUARE_",
        extra="ignore",
    )

    @property
    def app_id(self) -> str:
        """Backward compatibility for app_id."""
        return self.square_app_id

    @property
    def app_secret(self) -> str:
        """Backward compatibility for app_secret."""
        return self.square_app_secret

    @property
    def access_token(self) -> str:
        """Backward compatibility for access_token."""
        return self.developer_access_token


class ShopifySettings(BaseSettings):
    """
    Settings for the Shopify API.
    """

    api_key: str
    api_secret: str
    access_token: str
    environment: str = "development"
    redirect_uri: str = "http://localhost:8000/shopify/oauth/callback"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SHOPIFY_",
        extra="ignore",
    )
