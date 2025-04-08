"""
Database models used for OAuth token storage and merchant-related data.
"""

import datetime

from sqlalchemy import DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

from retail_backend.core.database import Base


class OAuthToken(Base):
    """
    Represents an OAuth token associated with a merchant.

    Attributes:
        merchant_id (str): Unique identifier for the merchant.
        access_token (str): OAuth access token for authenticating API requests.
        environment (str): Specifies if the token is for 'sandbox' or 'production'.
        created_at (datetime): Timestamp when the OAuth token was created.
        private_key (str): Private key for Synvya integration.
    """

    __tablename__ = "oauth_tokens"

    merchant_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    access_token: Mapped[str] = mapped_column(String, nullable=False)
    environment: Mapped[str] = mapped_column(String, default="sandbox", nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP")
    )
    private_key: Mapped[str | None] = mapped_column(String, nullable=True)
