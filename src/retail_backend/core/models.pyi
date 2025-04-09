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

from retail_backend.core.database import Base

class OAuthToken(Base):
    """
    Represents an OAuth token used for authentication.

    Attributes:
        merchant_id (str): The ID of the merchant associated with the token.
        access_token (str): The access token used for authentication.
        environment (str): The environment in which the token is used (e.g., sandbox, production).
        created_at (datetime.datetime): The timestamp when the token was created.
        private_key (str | None): The private key associated with the token.
    """

    merchant_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    access_token: Mapped[str] = mapped_column(String, nullable=False)
    environment: Mapped[str] = mapped_column(String, default="sandbox", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    private_key: Mapped[str | None] = mapped_column(String, nullable=True)

    def __init__(
        self,
        merchant_id: str,
        access_token: str,
        environment: str = "sandbox",
        created_at: datetime | None = None,
        private_key: str | None = None,
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
    profile_type: str
    website: str
    public_key: Optional[str]
    profile_url: Optional[str]

    @classmethod
    def from_square_data(cls, client: Client) -> "MerchantProfile": ...
