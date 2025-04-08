"""Square plugin module."""

from pathlib import Path
from typing import Any, Generator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import and_
from sqlalchemy.orm import Session
from square.client import Client
from synvya_sdk import Profile, generate_keys

from retail.core.auth import TokenData, create_access_token, get_current_merchant
from retail.core.database import SessionLocal
from retail.core.models import OAuthToken
from retail.core.settings import SQUARE_OAUTH_REDIRECT_URI, SquareSettings


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
    async def initiate_oauth() -> RedirectResponse:
        """Initiate OAuth flow."""
        scope = "MERCHANT_PROFILE_READ ITEMS_READ"

        oauth_url = (
            f"{square_base_url}/oauth2/authorize?"
            f"client_id={settings.app_id}&"
            f"scope={scope}&"
            f"redirect_uri={SQUARE_OAUTH_REDIRECT_URI}&"
            f"response_type=code"
        )
        print(f"OAuth URL: {oauth_url}")
        return RedirectResponse(oauth_url)

    @router.get("/oauth/callback")
    async def oauth_callback(request: Request, code: str, db: Session = Depends(get_db)) -> dict:
        """Handle OAuth callback."""
        oauth_api = client.o_auth
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
            print(f"Result: {result.body}")
            merchant_id = result.body["merchant_id"]
            access_token = result.body["access_token"]

            # Initialize scopes with a default value
            scopes = []

            # Add Token Status check here
            token_status_result = oauth_api.retrieve_token_status()
            if token_status_result.is_success():
                scopes = token_status_result.body.get("scopes", [])
                print(f"Verified scopes: {scopes}")
            else:
                raise HTTPException(status_code=400, detail=token_status_result.errors)

            print(
                f"OAuth successful: merchant_id={merchant_id}, access_token={access_token}, scopes={scopes}"
            )

            # Check if merchant already exists in the database
            existing_token = db.query(OAuthToken).filter_by(merchant_id=merchant_id).first()

            if existing_token:
                # Update only the access token for existing merchants
                existing_token.access_token = access_token
                db.commit()
                private_key = existing_token.private_key
            else:
                # Generate a new private key only for new merchants
                keys = generate_keys(env_var="", env_path=Path("/dev/null"))
                private_key = keys.get_private_key()

                # Create a new token entry for new merchants
                new_token = OAuthToken(
                    merchant_id=merchant_id,
                    access_token=access_token,
                    private_key=private_key,
                )
                db.add(new_token)
                db.commit()

            # Generate JWT token
            jwt_token = create_access_token(merchant_id)

            return {
                "message": "OAuth successful",
                "merchant_id": merchant_id,
                "private_key": private_key,
                "access_token": jwt_token,
            }
        else:
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

        return {
            "merchant": merchant_response.body["merchant"],
            "products": catalog_response.body.get("objects", []),
        }

    @router.get("/profile")
    async def get_merchant_profile(
        current_merchant: TokenData = Depends(get_current_merchant),
        db: Session = Depends(get_db),
    ) -> dict:
        """Get merchant's Nostr profile."""
        # Get the merchant's credentials from the database
        square_credentials = get_square_credentials(current_merchant, db)

        # Create a new client with the merchant's access token
        merchant_client = Client(
            access_token=square_credentials.access_token,
            environment="sandbox",
        )

        merchant_info = get_merchant_info(merchant_client)

        if not square_credentials.private_key:
            raise HTTPException(
                status_code=404,
                detail="Private key not found for merchant",
            )

        profile = populate_synvya_profile(merchant_info, square_credentials.private_key)
        return {
            "merchant_id": current_merchant.merchant_id,
            "profile": profile.dict(),
        }

    @router.post("/profile/publish")
    async def publish_profile(
        current_merchant: TokenData = Depends(get_current_merchant),
        db: Session = Depends(get_db),
    ) -> dict:
        """Publish merchant's Nostr profile."""
        # Get the merchant's credentials from the database
        square_credentials = get_square_credentials(current_merchant, db)

        # Create a new client with the merchant's access token
        merchant_client = Client(
            access_token=square_credentials.access_token,
            environment="sandbox",
        )

        merchant_info = get_merchant_info(merchant_client)

        if not square_credentials.private_key:
            raise HTTPException(
                status_code=404,
                detail="Private key not found for merchant",
            )

        profile = populate_synvya_profile(merchant_info, square_credentials.private_key)
        try:
            # TODO: Implement profile publishing using Synvya SDK
            return {"message": "Profile published successfully"}
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to publish profile: {str(e)}",
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


def populate_synvya_profile(merchant_data: dict, private_key: str) -> Profile:
    """
    Populates a Synvya Profile instance with data retrieved from Square merchant info.

    Args:
        merchant_data (dict): Merchant details from Square API.
        private_key (str): Merchant NostrKeys for profile creation.

    Returns:
        Profile: A populated Profile instance ready for publishing on Nostr.
    """
    profile = Profile(private_key)

    return profile
