"""Square plugin module."""

import uuid
from pathlib import Path

import requests  # type: ignore
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import and_
from sqlalchemy.orm import Session
from square.client import Client  # type: ignore
from synvya_sdk import Profile, generate_keys

from retail.core.database import SessionLocal
from retail.core.models import OAuthToken
from retail.core.settings import (
    SQUARE_OAUTH_REDIRECT_URI,
    SQUARE_VERSION,
    SquareSettings,
)


def get_db():
    """Dependency to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_square_router(
    client: Client,
    settings: SquareSettings,
    square_base_url: str,
    square_api_url: str,
) -> APIRouter:
    """Create a router for the Square API."""

    router = APIRouter()

    @router.get("/oauth")
    async def initiate_oauth():
        """Initiate OAuth flow."""
        scope = "MERCHANT_PROFILE_READ MERCHANT_PROFILE_WRITE ITEMS_READ"

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
    async def oauth_callback(
        request: Request, code: str, db: Session = Depends(get_db)
    ):
        """Handle OAuth callback."""
        private_key: str | None = None
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
            merchant_id = result.body["merchant_id"]
            access_token = result.body["access_token"]

            scopes = []

            # Token status check
            token_status_result = oauth_api.retrieve_token_status()
            if token_status_result.is_success():
                scopes = token_status_result.body.get("scopes", [])

                if "MERCHANT_PROFILE_WRITE" not in scopes:
                    raise HTTPException(
                        status_code=403,
                        detail="MERCHANT_PROFILE_WRITE scope missing from token.",
                    )
            else:
                raise HTTPException(status_code=400, detail=token_status_result.errors)

            # Create custom attribute definition
            # Assign a new private key to the merchant
            try:
                create_private_key_attribute(settings.access_token, square_api_url)

                keys = generate_keys(env_var="", env_path=Path("/dev/null"))
                private_key = keys.get_private_key()
                store_merchant_private_key(merchant_id, private_key, client)

            except HTTPException as e:
                raise e

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 409:
                    private_key = get_merchant_private_key(merchant_id, client)
                    if private_key is None:
                        # attribute defined but empty
                        keys = generate_keys(env_var="", env_path=Path("/dev/null"))
                        store_merchant_private_key(
                            merchant_id, keys.get_private_key(), client
                        )
                        private_key = keys.get_private_key()
                else:
                    raise HTTPException(
                        status_code=e.response.status_code,
                        detail=f"Square API Error: {e.response.text}",
                    ) from e

            existing_token = (
                db.query(OAuthToken).filter_by(merchant_id=merchant_id).first()
            )

            if existing_token:
                existing_token.access_token = access_token
            else:
                new_token = OAuthToken(
                    merchant_id=merchant_id, access_token=access_token
                )
                db.add(new_token)

            db.commit()
            return {
                "message": "OAuth successful",
                "merchant_id": merchant_id,
                "private_key": private_key,
            }
        else:
            raise HTTPException(status_code=400, detail=result.errors)

    @router.get("/seller/info/{merchant_id}")
    async def seller_info(merchant_id: str, db: Session = Depends(get_db)):
        """Get merchant information."""
        token_entry = (
            db.query(OAuthToken)
            .filter(
                and_(
                    OAuthToken.environment == "sandbox",
                    OAuthToken.merchant_id == merchant_id,
                )
            )
            .first()
        )

        if not token_entry:
            raise HTTPException(
                status_code=404, detail="Merchant OAuth token not found"
            )

        merchant_response = client.merchants.retrieve_merchant("me")
        if not merchant_response.is_success():
            raise HTTPException(status_code=400, detail=merchant_response.errors)

        catalog_response = client.catalog.list_catalog()
        if not catalog_response.is_success():
            raise HTTPException(status_code=400, detail=catalog_response.errors)

        return {
            "merchant": merchant_response.body["merchant"],
            "products": catalog_response.body.get("objects", []),
        }

    return router


def get_merchant_info(client: Client) -> dict:
    """
    Retrieves merchant details from the Square API using the provided OAuth token.

    Args:
        client (Client): Square client for authenticating requests.

    Returns:
        dict: Merchant details as provided by Square.

    Raises:
        requests.HTTPError: If the API request fails.
    """
    response = client.merchants.retrieve_merchant(merchant_id="me")

    if response.is_success():
        merchant_info = response.body.get("merchant")
        print(f"Merchant info fetched: {merchant_info}")
        return merchant_info
    else:
        error_detail = response.errors
        print(f"Error fetching merchant info: {error_detail}")
        raise HTTPException(status_code=400, detail=error_detail)


def get_merchant_private_key(
    merchant_id: str,
    client: Client,
) -> str | None:
    """
    Fetches the stored merchant private key from Square's Merchant Custom Attributes.

    Args:
        merchant_id (str): Square Merchant ID.
        client (Client): The Square client to use.
    Returns:
        str | None: Private key if exists, otherwise None.
    """

    result = client.merchant_custom_attributes.retrieve_merchant_custom_attribute(
        merchant_id=merchant_id, key="synvya_private_key", with_definition=False
    )

    if result.is_success():
        custom_attribute = result.body.get("custom_attribute")
        if custom_attribute:
            value = custom_attribute.get("value")
            print(f"Private key fetched: {value}")
            return value
        return None

    if result.is_error():
        errors = result.errors
        if any(e["code"] == "NOT_FOUND" for e in errors):
            print("Private key not found.")
            return None
        print(f"Error fetching private key: {errors}")
        raise HTTPException(status_code=400, detail=errors)

    return None


def store_merchant_private_key(
    merchant_id: str,
    private_key: str,
    client: Client,
) -> None:
    """
    Stores the merchant's private key as a Merchant Custom Attribute in Square.

    Args:
        merchant_id (str): Square Merchant ID.
        private_key (str): The private key to store.
        client (Client): The Square client to use.
    """
    result = client.merchant_custom_attributes.upsert_merchant_custom_attribute(
        merchant_id=merchant_id,
        key="synvya_private_key",
        body={"custom_attribute": {"value": private_key, "version": 1}},
    )

    if result.is_success():
        pass
    else:
        error_detail = result.errors
        print(f"Error storing private key for merchant {merchant_id}: {error_detail}")
        raise HTTPException(status_code=400, detail=error_detail)


def create_private_key_attribute(
    app_access_token: str,
    square_api_url: str,
) -> None:
    """
    Creates a custom attribute definition for synvya_private_key using the Square API.

    Args:
        app_access_token (str): The Square app access token to use.
        square_api_url (str): The Square API URL to use.
    """
    headers = {
        "Authorization": f"Bearer {app_access_token}",
        "Square-Version": SQUARE_VERSION,
        "Content-Type": "application/json",
    }

    url = f"{square_api_url}/merchants/custom-attribute-definitions"

    payload = {
        "custom_attribute_definition": {
            "key": "synvya_private_key",
            "name": "Synvya Private Key",
            "description": "Private key for Synvya integration",
            "schema": {
                "$ref": "https://developer-production-s.squarecdn.com/schemas/v1/common.json#squareup.common.String"
            },
            "visibility": "VISIBILITY_READ_WRITE_VALUES",
        },
        "idempotency_key": str(uuid.uuid4()),
    }

    response = requests.post(url, json=payload, headers=headers, timeout=30)

    # Enhanced error handling
    if response.status_code == 409:
        pass
    elif response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Square API Error: {response.text}",
        )

    return response.json()


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
