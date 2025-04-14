# pylint: disable=missing-docstring,unused-argument
"""
Database models used for OAuth token storage and merchant-related data.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy import DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column
from square.client import Client
from synvya_sdk import ProfileType

from retail_backend.core.database import Base

class SquareMerchantCredentials(Base):
    """
    Represents Square merchant credentials including OAuth token and Nostr integration.

    Attributes:
        merchant_id (str): Unique identifier for the merchant.
        square_merchant_token (str): Square OAuth access token for authenticating API requests.
        environment (str): Specifies if the token is for 'sandbox' or 'production'.
        created_at (datetime): Timestamp when the credentials were created.
        nostr_private_key (str): Private key for Nostr integration.
    """

    merchant_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    square_merchant_token: Mapped[str] = mapped_column("access_token", String, nullable=False)
    environment: Mapped[str] = mapped_column(String, default="sandbox", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    nostr_private_key: Mapped[str | None] = mapped_column("private_key", String, nullable=True)

    def __init__(
        self,
        merchant_id: str,
        square_merchant_token: str,
        environment: str = "sandbox",
        created_at: datetime | None = None,
        nostr_private_key: str | None = None,
    ) -> None: ...

class MerchantProfile(BaseModel):
    """
    Merchant profile data model.

    This model mirrors the structure of the Profile class in synvya_sdk,
    and is used for both API requests and responses.
    """

    name: str
    about: str
    banner: str
    bot: bool
    display_name: str
    hashtags: List[str]
    locations: List[str]
    namespace: str
    nip05: str
    picture: str
    profile_type: ProfileType
    website: str
    public_key: Optional[str]
    profile_url: Optional[str]

    @classmethod
    def from_square_data(cls, client: Client) -> "MerchantProfile": ...

# Alias for backward compatibility
OAuthToken = SquareMerchantCredentials
