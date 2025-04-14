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
from retail_backend.core.merchant import get_nostr_profile, set_nostr_profile, set_nostr_stall
from retail_backend.core.models import MerchantProfile, SquareMerchantCredentials
from retail_backend.core.settings import Provider, SquareSettings

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
) -> SquareMerchantCredentials:
    """Get Square credentials for the authenticated merchant."""
    credentials = (
        db.query(SquareMerchantCredentials)
        .filter(
            and_(
                SquareMerchantCredentials.environment == "sandbox",
                SquareMerchantCredentials.merchant_id == current_merchant.merchant_id,
            )
        )
        .first()
    )

    if not credentials:
        raise HTTPException(status_code=404, detail="Merchant OAuth token not found")

    return credentials


def create_square_router(
    client: Client,
    settings: SquareSettings,
    square_base_url: str,
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
            f"client_id={settings.square_app_id}&"
            f"scope={scope}&"
            f"redirect_uri={settings.square_redirect_uri}&"
            f"response_type=code&"
            f"state={state}"
        )
        print(f"OAuth URL: {oauth_url}")
        return RedirectResponse(oauth_url)

    @router.get("/oauth/callback")
    async def oauth_callback(
        request: Request, code: str, state: str | None = None, db: Session = Depends(get_db)
    ) -> RedirectResponse:
        """
        Handle OAuth callback from Square.

        For first-time succesful authorization:
        - Creates a new Nostr private key for the merchant
        - Publishes the merchant's Nostr profile

        For all succesful authorizations:
        - Retrieves the merchant's access token and merchant ID
        - Publishes the merchant's catalog to Nostr
        - Creates a Synvya token entry for the merchant in the database
        - Generates a JWT token for the frontend
        - Constructs a redirect URL with the JWT token, merchant ID, and profile published status


        Args:
            request (Request): The incoming request object.
            code (str): The authorization code from Square.
            state (str | None): The state parameter from the initial request.
            db (Session): The database session.
        """
        logger.info("OAuth callback received: code=%s... state=%s", code[:5], state)
        logger.info("Request headers: %s", dict(request.headers))
        oauth_api = client.o_auth
        logger.info("Obtaining token from Square API")
        result = oauth_api.obtain_token(
            body={
                "client_id": settings.app_id,
                "client_secret": settings.app_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.square_redirect_uri,
            }
        )

        if not result.is_success():
            logger.error("Error obtaining token from Square API: %s", result.errors)
            raise HTTPException(status_code=400, detail=result.errors)

        logger.info("Successfully obtained token from Square API")
        merchant_id = result.body["merchant_id"]
        access_token = result.body["access_token"]

        # Check if merchant already exists in the database
        existing_credentials = (
            db.query(SquareMerchantCredentials).filter_by(merchant_id=merchant_id).first()
        )

        profile_published = False

        if existing_credentials:
            # Update only the access token for existing merchants
            logger.info("Updating existing merchant: %s", merchant_id)
            existing_credentials.square_merchant_token = access_token
            db.commit()
            private_key = existing_credentials.nostr_private_key
            if private_key is None:
                raise HTTPException(status_code=400, detail="Private key not found for merchant")
        else:
            # Generate a new private key only for new merchants
            logger.info("Creating new merchant: %s", merchant_id)
            keys = generate_keys(env_var="", env_path=Path("/dev/null"))
            private_key = keys.get_private_key()

            # Create a new token entry for new merchants
            new_credentials = SquareMerchantCredentials(
                merchant_id=merchant_id,
                square_merchant_token=access_token,
                nostr_private_key=private_key,
            )
            db.add(new_credentials)
            db.commit()

            # Create a Square client with the merchant's access token
            logger.info("Creating Square client with merchant token")
            merchant_square_client = Client(
                access_token=access_token, environment=settings.environment
            )
            # Publish profile for new merchants
            try:
                profile = MerchantProfile.from_square_data(merchant_square_client)
                await set_nostr_profile(profile, private_key)
                profile_published = True
            except Exception as e:
                logger.error("Error publishing profile (continuing OAuth flow): %s", str(e))

        # Generate JWT token
        logger.info("Generating JWT token")
        frontend_auth_token = create_access_token(merchant_id)

        # Use the state parameter as the frontend callback URL or use default
        frontend_callback_url = state or "http://localhost:3000/auth/callback"
        logger.info("Frontend callback URL: %s", frontend_callback_url)

        # Construct redirect URL without the private key
        redirect_url = (
            f"{frontend_callback_url}?"
            f"access_token={quote(str(frontend_auth_token))}&"
            f"merchant_id={quote(str(merchant_id))}&"
            f"profile_published={str(profile_published).lower()}"
        )

        logger.info(
            "Redirecting to: %s with profile_published=%s",
            frontend_callback_url,
            profile_published,
        )

        # Redirect to frontend
        return RedirectResponse(url=redirect_url)

    @router.get("/seller/info")
    async def seller_info(
        square_credentials: SquareMerchantCredentials = Depends(get_square_credentials),
    ) -> dict:
        """Get merchant information."""
        # Create a new client with the merchant's access token
        merchant_client = Client(
            access_token=square_credentials.square_merchant_token,
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
        logger.info("Getting profile for merchant: %s", current_merchant.merchant_id)

        # Get the merchant's credentials from the database
        try:
            square_credentials = get_square_credentials(current_merchant, db)
            logger.info("Retrieved merchant credentials from database")
        except HTTPException as e:
            logger.error("Error retrieving credentials: %s", str(e))
            raise

        if not square_credentials.nostr_private_key:
            logger.error("Private key not found for merchant")
            raise HTTPException(
                status_code=404,
                detail="Private key not found for merchant",
            )

        # Get the profile from Nostr
        try:
            logger.info("Fetching profile from Nostr")
            profile = await get_nostr_profile(square_credentials.nostr_private_key)
            logger.info(
                "Successfully retrieved profile for merchant: %s", current_merchant.merchant_id
            )
            return profile
        except HTTPException as e:
            logger.error("Error fetching profile: %s", str(e))
            raise
        except Exception as e:
            logger.error("Unexpected error fetching profile: %s", str(e))
            raise HTTPException(status_code=500, detail=f"Server error: {str(e)}") from e

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
        logger.info("Publishing profile for merchant: %s", current_merchant.merchant_id)
        logger.info(
            "Profile data: name=%s, display_name=%s",
            profile_request.name,
            profile_request.display_name,
        )

        # Get the merchant's credentials from the database
        try:
            square_credentials = get_square_credentials(current_merchant, db)
            logger.info("Retrieved merchant credentials from database")
        except HTTPException as e:
            logger.error("Error retrieving credentials: %s", str(e))
            raise

        if not square_credentials.nostr_private_key:
            logger.error("Private key not found for merchant")
            raise HTTPException(
                status_code=404,
                detail="Private key not found for merchant",
            )

        private_key = square_credentials.nostr_private_key

        try:
            # Delegate profile creation and publishing to merchant.py
            logger.info("Attempting to publish profile to Nostr")
            await set_nostr_profile(profile_request, private_key)
            logger.info(
                "Successfully published profile for merchant: %s", current_merchant.merchant_id
            )

            return {"message": "Profile published successfully"}

        except ValueError as e:
            logger.error("Failed to publish profile - value error: %s", str(e))
            raise HTTPException(
                status_code=400,
                detail=f"Failed to publish profile: {str(e)}",
            ) from e
        except Exception as e:
            logger.error("Server error publishing profile: %s", str(e))
            raise HTTPException(
                status_code=500,
                detail=f"Server error publishing profile: {str(e)}",
            ) from e

    @router.post("/locations/publish", response_model=dict)
    async def publish_locations(
        current_merchant: TokenData = Depends(get_current_merchant),
        db: Session = Depends(get_db),
    ) -> dict:
        """Publish merchant's locations as Nostr Stalls."""
        logger.info("Publishing locations for merchant: %s", current_merchant.merchant_id)

        # Get the merchant's credentials from the database
        try:
            square_credentials = get_square_credentials(current_merchant, db)
            logger.info("Retrieved merchant credentials from database")
        except HTTPException as e:
            logger.error("Error retrieving credentials: %s", str(e))
            raise

        if not square_credentials.nostr_private_key:
            logger.error("Private key not found for merchant")
            return {"message": "Failed to publish locations: Private key not found for merchant"}

        private_key = square_credentials.nostr_private_key

        merchant_square_client = Client(
            access_token=square_credentials.square_merchant_token,
            environment="sandbox",
        )

        locations_response = merchant_square_client.locations.list_locations()

        if not locations_response.is_success():
            logger.error("Error fetching locations: %s", locations_response.errors)
            return {"message": "Failed to publish locations: Error fetching locations"}

        locations = locations_response.body.get("locations", [])

        locations_published = 0
        locations_failed = 0

        for location in locations:
            logger.info("Publishing location as Nostr Stall: %s", location)
            published = await set_nostr_stall(Provider.SQUARE, location, private_key)
            if published:
                locations_published += 1
            else:
                locations_failed += 1

        return {
            "locations_published": locations_published,
            "locations_failed": locations_failed,
        }

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
