# pylint: disable=missing-docstring,unused-argument
"""
Settings for the retail application.
"""

from enum import Enum

from pydantic_settings import BaseSettings

SQUARE_VERSION = "2025-03-19"
SQUARE_BASE_URL_SANDBOX = "https://connect.squareupsandbox.com"
SQUARE_BASE_URL_PRODUCTION = "https://connect.squareup.com"
SQUARE_OAUTH_REDIRECT_URI = "http://localhost:8000/square/oauth/callback"

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

    @property
    def app_id(self) -> str: ...
    @property
    def app_secret(self) -> str: ...
    @property
    def access_token(self) -> str: ...

class ShopifySettings(BaseSettings):
    """
    Settings for the Shopify API.
    """

    api_key: str = ""
    api_secret: str = ""
    access_token: str = ""
    environment: str = "development"
    redirect_uri: str = "http://localhost:8000/shopify/oauth/callback"

def get_settings(provider: Provider) -> SquareSettings | ShopifySettings: ...
