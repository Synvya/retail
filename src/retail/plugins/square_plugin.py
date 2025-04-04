"""Square plugin module."""

import os
from pathlib import Path

import requests  # type: ignore
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import and_
from sqlalchemy.orm import Session
from square.client import Client  # type: ignore
from synvya_sdk import NostrKeys, Profile, generate_keys

from retail.core.database import SessionLocal
from retail.core.models import OAuthToken
from retail.core.profile_ops import (
    create_synvya_private_key_definition,
    get_square_api_base_url,
)

load_dotenv()

router = APIRouter()

client_id = os.getenv("SQUARE_APP_ID")
client_secret = os.getenv("SQUARE_APP_SECRET")
environment = os.getenv("SQUARE_ENVIRONMENT", "sandbox")

seller_client = Client(
    access_token=os.getenv("SQUARE_ACCESS_TOKEN"),
    environment=environment,
    square_version="2025-03-19",
)

SQUARE_API_BASE_URL = "https://connect.squareup.com/v2"


def get_db():
    """Dependency to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/oauth")
async def initiate_oauth():
    """Initiate OAuth flow."""
    scope = "MERCHANT_PROFILE_READ MERCHANT_PROFILE_WRITE ITEMS_READ"
    base_url = (
        "https://connect.squareupsandbox.com"
        if environment == "sandbox"
        else "https://connect.squareup.com"
    )
    oauth_url = (
        f"{base_url}/oauth2/authorize?client_id={client_id}&scope={scope}&session=False"
        f"&redirect_uri=http://localhost:8000/square/oauth/callback"
    )
    return RedirectResponse(oauth_url)


@router.get("/oauth/callback")
async def oauth_callback(request: Request, code: str, db: Session = Depends(get_db)):
    """Handle OAuth callback."""
    oauth_api = seller_client.o_auth
    result = oauth_api.obtain_token(
        body={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": "http://localhost:8000/square/oauth/callback",
        }
    )
    if result.is_success():
        merchant_id = result.body["merchant_id"]
        access_token = result.body["access_token"]

        print(
            f"OAuth successful: merchant_id={merchant_id}, access_token={access_token}"
        )

        # Create custom attribute definition
        try:
            create_synvya_private_key_definition(access_token, environment)
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 409:
                # Already exists; safe to ignore or log this case
                pass
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to create custom attribute definition: {str(e)}",
                ) from e

        existing_token = db.query(OAuthToken).filter_by(merchant_id=merchant_id).first()

        if existing_token:
            existing_token.access_token = access_token
        else:
            new_token = OAuthToken(merchant_id=merchant_id, access_token=access_token)
            db.add(new_token)

        db.commit()
        return {"message": "OAuth successful", "merchant_id": merchant_id}
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
        raise HTTPException(status_code=404, detail="Merchant OAuth token not found")

    # Create a Square client with merchant's OAuth token
    merchant_client = Client(
        access_token=token_entry.access_token,
        environment=environment,
        square_version="2024-03-20",
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


def get_square_merchant_info(oauth_token: str, env: str) -> dict:
    """Get merchant information from Square."""
    headers = {
        "Authorization": f"Bearer {oauth_token}",
        "Square-Version": "2024-03-20",
        "Content-Type": "application/json",
    }
    url = f"{get_square_api_base_url(env)}/merchants/me"
    response = requests.get(url, headers=headers, timeout=30)

    print(f"Merchant info fetched: {response.json()}")

    response.raise_for_status()
    return response.json().get("merchant")


def get_merchant_private_key(
    oauth_token: str, merchant_id: str, env: str
) -> str | None:
    """Get merchant private key from Square."""
    headers = {
        "Authorization": f"Bearer {oauth_token}",
        "Square-Version": "2024-03-20",
        "Content-Type": "application/json",
    }
    url = (
        f"{get_square_api_base_url(env)}/merchants/{merchant_id}/"
        "custom-attributes/synvya_private_key?with_definition=false"
    )
    response = requests.get(url, headers=headers, timeout=30)

    print(f"Private key fetched response: {response.status_code}, {response.text}")

    if response.status_code == 200:
        custom_attribute = response.json().get("custom_attribute")
        return custom_attribute.get("value") if custom_attribute else None
    elif response.status_code == 404:
        return None

    response.raise_for_status()
    return None


def store_merchant_private_key(
    oauth_token: str, merchant_id: str, private_key: str, env: str
) -> None:
    """Store merchant private key in Square using Square SDK."""
    client = Client(
        access_token=oauth_token,
        environment=env,
        square_version="2024-04-17",
    )

    result = client.merchant_custom_attributes.upsert_merchant_custom_attribute(
        merchant_id=merchant_id,
        key="synvya_private_key",
        body={"custom_attribute": {"value": private_key}},
    )

    if result.is_success():
        print(f"Successfully stored private key for merchant {merchant_id}.")
    else:
        error_detail = result.errors
        print(f"Error storing private key for merchant {merchant_id}: {error_detail}")
        raise HTTPException(status_code=400, detail=error_detail)


def get_or_generate_merchant_keys(
    oauth_token: str, merchant_id: str, env: str
) -> NostrKeys:
    """Get or generate merchant keys."""
    private_key = get_merchant_private_key(oauth_token, merchant_id, env)

    if private_key:
        keys = NostrKeys.from_private_key(private_key)
    else:
        keys = generate_keys(env_var="", env_path=Path("/dev/null"))
        store_merchant_private_key(oauth_token, merchant_id, keys.private_key, env)

    return keys


def populate_synvya_profile(merchant_data: dict, keys: NostrKeys) -> Profile:
    """Populate Synvya profile."""
    profile = Profile(keys.private_key)
    return profile


def fetch_and_prepare_profile(oauth_token: str, env: str) -> Profile:
    """Fetch and prepare Synvya profile."""
    merchant_info = get_square_merchant_info(oauth_token, env)
    merchant_id = merchant_info["id"]
    keys = get_or_generate_merchant_keys(oauth_token, merchant_id, env)
    synvya_profile = populate_synvya_profile(merchant_info, keys)
    return synvya_profile
