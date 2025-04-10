"""Square plugin module.

This module provides API endpoints for the Square integration in the retail backend,
including OAuth authentication, merchant information retrieval, and Nostr profile
management for merchants.

The profile publishing functionality allows merchants to create and publish
their profiles to the Nostr network, enabling decentralized identity and
discovery for Square merchants.
"""

import logging
from pathlib import Path
from typing import Any, Generator
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import and_
from sqlalchemy.orm import Session
from square.client import Client
from synvya_sdk import generate_keys

from retail_backend.core.auth import TokenData, create_access_token, get_current_merchant
from retail_backend.core.database import SessionLocal
from retail_backend.core.merchant import get_nostr_profile, set_nostr_profile
from retail_backend.core.models import MerchantProfile, OAuthToken
from retail_backend.core.settings import SQUARE_OAUTH_REDIRECT_URI, SquareSettings

# Setup module-level logger
logger = logging.getLogger("square")


def get_db() -> Generator[Session, None, None]:
    """Dependency to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_square_credentials(
    current_merchant: TokenData = Depends(get_current_merchant),
    db: Session = Depends(get_db),
) -> OAuthToken:
    """Get Square credentials for the authenticated merchant."""
    token_entry = (
        db.query(OAuthToken)
        .filter(
            and_(
                OAuthToken.environment == "sandbox",
                OAuthToken.merchant_id == current_merchant.merchant_id,
            )
        )
        .first()
    )

    if not token_entry:
        raise HTTPException(status_code=404, detail="Merchant OAuth token not found")

    return token_entry


def create_square_router(
    client: Client,
    settings: SquareSettings,
    square_base_url: str,
    square_api_url: str,
) -> APIRouter:
    """Create a router for the Square API."""

    router = APIRouter()

    @router.get("/oauth")
    async def initiate_oauth(redirect_uri: str | None = None) -> RedirectResponse:
        """Initiate OAuth flow."""
        scope = "MERCHANT_PROFILE_READ ITEMS_READ"

        # Create state parameter with redirect_uri to retrieve it in callback
        state = redirect_uri or "http://localhost:3000/auth/callback"

        oauth_url = (
            f"{square_base_url}/oauth2/authorize?"
            f"client_id={settings.app_id}&"
            f"scope={scope}&"
            f"redirect_uri={SQUARE_OAUTH_REDIRECT_URI}&"
            f"response_type=code&"
            f"state={state}"
        )
        print(f"OAuth URL: {oauth_url}")
        return RedirectResponse(oauth_url)

    @router.get("/oauth/callback")
    async def oauth_callback(
        request: Request, code: str, state: str | None = None, db: Session = Depends(get_db)
    ) -> RedirectResponse:
        """Handle OAuth callback."""
        logger.info(f"OAuth callback received: code={code[:5]}... state={state}")
        logger.info(f"Request headers: {dict(request.headers)}")

        oauth_api = client.o_auth
        logger.info("Obtaining token from Square API")
        result = oauth_api.obtain_token(
            body={
                "client_id": settings.app_id,
                "client_secret": settings.app_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": SQUARE_OAUTH_REDIRECT_URI,
            }
        )
        if result.is_success():
            logger.info("Successfully obtained token from Square API")
            merchant_id = result.body["merchant_id"]
            access_token = result.body["access_token"]

            # Initialize scopes with a default value
            scopes = []

            # Add Token Status check here
            logger.info("Retrieving token status")
            token_status_result = oauth_api.retrieve_token_status()
            if token_status_result.is_success():
                scopes = token_status_result.body.get("scopes", [])
                logger.info(f"Token scopes: {scopes}")
            else:
                logger.error(f"Token status error: {token_status_result.errors}")
                raise HTTPException(status_code=400, detail=token_status_result.errors)

            # Check if merchant already exists in the database
            logger.info(f"Checking if merchant exists: {merchant_id}")
            existing_token = db.query(OAuthToken).filter_by(merchant_id=merchant_id).first()

            if existing_token:
                # Update only the access token for existing merchants
                logger.info(f"Updating existing merchant: {merchant_id}")
                existing_token.access_token = access_token
                db.commit()
                private_key = existing_token.private_key
            else:
                # Generate a new private key only for new merchants
                logger.info(f"Creating new merchant: {merchant_id}")
                keys = generate_keys(env_var="", env_path=Path("/dev/null"))
                private_key = keys.get_private_key()
                logger.info(
                    f"Generated new private key for merchant (first 5 chars): {private_key[:5]}..."
                )

                # Create a new token entry for new merchants
                new_token = OAuthToken(
                    merchant_id=merchant_id,
                    access_token=access_token,
                    private_key=private_key,
                )
                db.add(new_token)
                db.commit()

            # Generate JWT token
            logger.info("Generating JWT token")
            jwt_token = create_access_token(merchant_id)

            # Create a Square client with the merchant's access token
            logger.info("Creating Square client with merchant token")
            merchant_square_client = Client(
                access_token=access_token, environment=settings.environment
            )

            # Try to publish the merchant's profile to Nostr
            profile_published = False
            if private_key is not None:
                try:
                    logger.info("Attempting to publish merchant profile to Nostr")
                    profile = MerchantProfile.from_square_data(merchant_square_client)
                    await set_nostr_profile(profile, private_key)
                    profile_published = True
                    logger.info("Successfully published merchant profile to Nostr")
                except Exception as e:
                    logger.error(f"Error publishing profile (continuing OAuth flow): {str(e)}")
                    profile_published = False
            else:
                logger.warning("Private key is None, skipping profile publishing")

            # Use the state parameter as the frontend callback URL or use default
            frontend_callback_url = state or "http://localhost:3000/auth/callback"
            logger.info(f"Frontend callback URL: {frontend_callback_url}")

            # Construct redirect URL without the private key
            redirect_url = (
                f"{frontend_callback_url}?"
                f"access_token={quote(str(jwt_token))}&"
                f"merchant_id={quote(str(merchant_id))}&"
                f"profile_published={str(profile_published).lower()}"
            )
            logger.info(
                f"Redirecting to: {frontend_callback_url} with profile_published={profile_published}"
            )

            # Redirect to frontend
            return RedirectResponse(url=redirect_url)
        else:
            logger.error(f"OAuth error: {result.errors}")
            raise HTTPException(status_code=400, detail=result.errors)

    @router.get("/seller/info")
    async def seller_info(
        square_credentials: OAuthToken = Depends(get_square_credentials),
    ) -> dict:
        """Get merchant information."""
        # Create a new client with the merchant's access token
        merchant_client = Client(
            access_token=square_credentials.access_token,
            environment="sandbox",
        )

        merchant_response = merchant_client.merchants.retrieve_merchant("me")
        if not merchant_response.is_success():
            raise HTTPException(status_code=400, detail=merchant_response.errors)

        catalog_response = merchant_client.catalog.list_catalog()
        if not catalog_response.is_success():
            raise HTTPException(status_code=400, detail=catalog_response.errors)

        # Retrieve merchant locations
        locations_response = merchant_client.locations.list_locations()
        if not locations_response.is_success():
            raise HTTPException(status_code=400, detail=locations_response.errors)

        return {
            "merchant": merchant_response.body["merchant"],
            "products": catalog_response.body.get("objects", []),
            "locations": locations_response.body.get("locations", []),
        }

    @router.get("/profile", response_model=MerchantProfile)
    async def get_merchant_profile(
        current_merchant: TokenData = Depends(get_current_merchant),
        db: Session = Depends(get_db),
    ) -> MerchantProfile:
        """Get merchant's Nostr profile."""
        logger.info(f"Getting profile for merchant: {current_merchant.merchant_id}")

        # Get the merchant's credentials from the database
        try:
            square_credentials = get_square_credentials(current_merchant, db)
            logger.info("Retrieved merchant credentials from database")
        except HTTPException as e:
            logger.error(f"Error retrieving credentials: {str(e)}")
            raise

        if not square_credentials.private_key:
            logger.error("Private key not found for merchant")
            raise HTTPException(
                status_code=404,
                detail="Private key not found for merchant",
            )

        # Get the profile from Nostr
        try:
            logger.info("Fetching profile from Nostr")
            profile = await get_nostr_profile(square_credentials.private_key)
            logger.info(
                f"Successfully retrieved profile for merchant: {current_merchant.merchant_id}"
            )
            return profile
        except HTTPException as e:
            logger.error(f"Error fetching profile: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching profile: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

    @router.post("/profile/publish", response_model=dict)
    async def publish_profile(
        profile_request: MerchantProfile,
        current_merchant: TokenData = Depends(get_current_merchant),
        db: Session = Depends(get_db),
    ) -> dict:
        """
        Publish merchant's Nostr profile.

        The endpoint accepts a MerchantProfile object with the profile data.
        All fields have default values except for 'name' which is required.
        The public_key and profile_url fields are ignored on input as they are
        derived from the merchant's private key.

        Returns:
            dict: A message indicating success or an error message
        """
        logger.info(f"Publishing profile for merchant: {current_merchant.merchant_id}")
        logger.info(
            f"Profile data: name={profile_request.name}, display_name={profile_request.display_name}"
        )

        # Get the merchant's credentials from the database
        try:
            square_credentials = get_square_credentials(current_merchant, db)
            logger.info("Retrieved merchant credentials from database")
        except HTTPException as e:
            logger.error(f"Error retrieving credentials: {str(e)}")
            raise

        if not square_credentials.private_key:
            logger.error("Private key not found for merchant")
            raise HTTPException(
                status_code=404,
                detail="Private key not found for merchant",
            )

        private_key = square_credentials.private_key

        try:
            # Delegate profile creation and publishing to merchant.py
            logger.info("Attempting to publish profile to Nostr")
            await set_nostr_profile(profile_request, private_key)
            logger.info(
                f"Successfully published profile for merchant: {current_merchant.merchant_id}"
            )

            return {"message": "Profile published successfully"}

        except ValueError as e:
            logger.error(f"Failed to publish profile - value error: {str(e)}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to publish profile: {str(e)}",
            )
        except Exception as e:
            logger.error(f"Server error publishing profile: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Server error publishing profile: {str(e)}",
            )

    return router


def get_merchant_info(client: Client) -> dict[str, Any]:
    """
    Retrieves merchant details from the Square API using the provided OAuth token.

    Args:
        client (Client): Square client for authenticating requests.

    Returns:
        dict[str, Any]: Merchant details as provided by Square.

    Raises:
        requests.HTTPError: If the API request fails.
    """
    response = client.merchants.retrieve_merchant(merchant_id="me")

    if response.is_success():
        merchant_info = response.body.get("merchant")
        print(f"Merchant info fetched: {merchant_info}")
        return dict(merchant_info)  # Cast to dict[str, Any]
    else:
        error_detail = response.errors
        print(f"Error fetching merchant info: {error_detail}")
        raise HTTPException(status_code=400, detail=error_detail)
