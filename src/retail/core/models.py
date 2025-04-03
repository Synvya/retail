"""
Database models used for OAuth token storage and merchant-related data.
"""

from sqlalchemy import Column, DateTime, String, text

from retail.core.database import Base


class OAuthToken(Base):
    """
    Represents an OAuth token associated with a merchant.

    Attributes:
        merchant_id (str): Unique identifier for the merchant.
        access_token (str): OAuth access token for authenticating API requests.
        created_at (datetime): Timestamp when the OAuth token was created.
    """

    __tablename__ = "oauth_tokens"

    merchant_id = Column(String, primary_key=True, index=True)
    access_token = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
