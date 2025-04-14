"""
Database models used for OAuth token storage and merchant-related data.
"""

import datetime
from typing import List, Optional

from pydantic import BaseModel, Field
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

    __tablename__ = "oauth_tokens"

    merchant_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    square_merchant_token: Mapped[str] = mapped_column("access_token", String, nullable=False)
    environment: Mapped[str] = mapped_column(String, default="sandbox", nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=text("CURRENT_TIMESTAMP")
    )
    nostr_private_key: Mapped[str | None] = mapped_column("private_key", String, nullable=True)


class MerchantProfile(BaseModel):
    """
    Merchant profile data model.

    This model mirrors the structure of the Profile class in synvya_sdk,
    and is used for both API requests and responses.
    """

    name: str = Field(..., description="Profile name (required)")
    about: str = Field("", description="Profile description")
    banner: str = Field("", description="URL to banner image")
    bot: bool = Field(False, description="Whether this profile represents a bot")
    display_name: str = Field("", description="Display name")
    hashtags: List[str] = Field([], description="List of hashtags")
    locations: List[str] = Field([], description="List of locations")
    namespace: str = Field("", description="Profile namespace")
    nip05: str = Field("", description="NIP-05 identifier")
    picture: str = Field("", description="URL to profile picture")
    profile_type: ProfileType = Field(ProfileType.OTHER_OTHER, description="Profile type")
    website: str = Field("", description="Website URL")
    # Read-only fields (returned by GET but not used in POST)
    public_key: Optional[str] = Field(None, description="Public key (derived from private key)")
    profile_url: Optional[str] = Field(None, description="Profile URL")

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Pressed On Main",
                "about": "100% organic juice and gluten free bakery",
                "banner": "https://example.com/banner.jpg",
                "bot": False,
                "display_name": "Pressed On Main Café",
                "hashtags": ["juice", "gluten free", "bakery"],
                "locations": ["San Francisco", "Los Angeles"],
                "namespace": "com.synvya.merchant",
                "nip05": "pressedonmain@synvya.com",
                "picture": "https://example.com/logo.png",
                "profile_type": ProfileType.MERCHANT_RESTAURANT,
                "website": "www.pressedonmain.com",
            }
        }
    }

    @classmethod
    def from_square_data(cls, client: Client) -> "MerchantProfile":
        """
        Create a MerchantProfile from Square data.

        Args:
            client (Client): Square client for authenticating requests.

        Returns:
            MerchantProfile: A MerchantProfile object.

        Raises:
            ValueError: If the Square data is invalid.
        """
        # Fetch merchant profile data from Square
        merchant_response = client.merchants.retrieve_merchant("me")
        if not merchant_response.is_success():
            raise ValueError("Failed to fetch merchant data from Square")

        catalog_response = client.catalog.list_catalog()
        if not catalog_response.is_success():
            raise ValueError("Failed to fetch catalog data from Square")

        # Retrieve merchant locations
        locations_response = client.locations.list_locations()
        if not locations_response.is_success():
            raise ValueError("Failed to fetch locations data from Square")

        merchant_data = merchant_response.body["merchant"]
        products = catalog_response.body.get("objects", [])
        locations = locations_response.body.get("locations", [])

        # Extract data from merchant_data
        name = merchant_data.get("id", "")
        nip05 = str(name) + "@synvya.com"
        display_name = merchant_data.get("business_name", "")

        # Extract data from locations if available
        if len(locations) > 0:
            about = locations[0].get("description", "")
            website = locations[0].get("website_url", "")
        else:
            about = ""
            website = ""

        # Extract data from catalog if available
        hashtags = []
        for product in products:
            if product.get("type", "") == "CATEGORY":
                if product.get("category_data", {}).get("name", ""):
                    hashtags.append(product.get("category_data", {}).get("name", ""))

        # Fields with no equivalent in Square
        banner = ""  # no info on Square for a banner
        bot = False
        locations = []
        namespace = "com.synvya.merchant"
        picture = ""
        profile_type = ProfileType.OTHER_OTHER

        # Create a MerchantProfile object
        profile = MerchantProfile(
            name=name,
            about=about,
            banner=banner,
            bot=bot,
            display_name=display_name,
            hashtags=hashtags,
            locations=locations,
            namespace=namespace,
            nip05=nip05,
            picture=picture,
            profile_type=profile_type,
            website=website,
            public_key="",  # Will be derived from private_key in set_nostr_profile
            profile_url="",  # Will be set in set_nostr_profile
        )

        return profile


# Alias for backward compatibility
OAuthToken = SquareMerchantCredentials
