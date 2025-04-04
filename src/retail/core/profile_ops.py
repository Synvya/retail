"""Fetch merchant profile from Square and prepare a Synvya Profile."""

import uuid
from pathlib import Path

import requests  # type: ignore
from fastapi import HTTPException
from square.client import Client  # type: ignore
from square.http.auth.o_auth_2 import BearerAuthCredentials  # type: ignore
from synvya_sdk import NostrKeys, Profile, generate_keys


def get_square_base_url(environment: str) -> str:
    """
    Retrieves the base URL for the Square API based on the environment.

    Args:
        environment (str): The environment to use (e.g., "sandbox" or "production").

    Returns:
        str: The base URL for the Square API.
    """
    return (
        "https://connect.squareupsandbox.com"
        if environment == "sandbox"
        else "https://connect.squareup.com"
    )


def get_square_api_base_url(environment: str) -> str:
    """
    Retrieves the base URL for the Square API.

    Args:
        environment (str): The environment to use (e.g., "sandbox" or "production").

    Returns:
        str: The base URL for the Square API.
    """
    return f"{get_square_base_url(environment)}/v2"


def get_square_merchant_info(oauth_token: str, env: str) -> dict:
    """
    Retrieves merchant details from the Square API using the provided OAuth token.

    Args:
        oauth_token (str): OAuth token for authenticating requests.

    Returns:
        dict: Merchant details as provided by Square.

    Raises:
        requests.HTTPError: If the API request fails.
    """
    client = Client(
        bearer_auth_credentials=BearerAuthCredentials(access_token=oauth_token),
        environment=env,
        square_version="2024-04-17",
    )

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
    oauth_token: str, merchant_id: str, env: str
) -> str | None:
    """
    Fetches the stored merchant private key from Square's Merchant Custom Attributes.

    Args:
        oauth_token (str): OAuth token for authenticating requests.
        merchant_id (str): Square Merchant ID.
        env (str): The environment to use (e.g., "sandbox" or "production").
    Returns:
        str | None: Private key if exists, otherwise None.
    """

    client = Client(
        bearer_auth_credentials=BearerAuthCredentials(access_token=oauth_token),
        environment=env,
        square_version="2024-04-17",
    )

    result = client.merchant_custom_attributes.retrieve_merchant_custom_attribute(
        merchant_id=merchant_id, key="synvya_private_key", with_definition=False
    )

    if result.is_success():
        custom_attribute = result.body.get("custom_attribute")
        if custom_attribute:
            value = custom_attribute.get("value")
            print(f"Private key fetched: {value}")
            return value
        else:
            return None
    elif result.is_error():
        errors = result.errors
        if any(e["code"] == "NOT_FOUND" for e in errors):
            print("Private key not found.")
            return None
        print(f"Error fetching private key: {errors}")
        raise HTTPException(status_code=400, detail=errors)

    return None


def store_merchant_private_key(
    oauth_token: str, merchant_id: str, private_key: str, environment: str
):
    """
    Stores the merchant's private key as a Merchant Custom Attribute in Square.

    Args:
        oauth_token (str): OAuth token for authenticating requests.
        merchant_id (str): Square Merchant ID.
        private_key (str): The private key to store.
        environment (str): The environment to use (e.g., "sandbox" or "production").
    """
    client = Client(
        access_token=oauth_token,
        environment=environment,
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
    oauth_token: str, merchant_id: str, environment: str
) -> NostrKeys:
    """
    Retrieves the merchant's private key stored as a Merchant Custom Attribute.
    If not found, generates new key pair and stores the private key.

    Args:
        oauth_token (str): OAuth token for authenticating requests.
        merchant_id (str): Square Merchant ID.
        environment (str): The environment to use (e.g., "sandbox" or "production").

    Returns:
        NostrKeys: Merchant's NostrKeys instance with private/public keys.
    """
    private_key = get_merchant_private_key(oauth_token, merchant_id, environment)

    if private_key:
        keys = NostrKeys.from_private_key(private_key)
    else:
        keys = generate_keys(env_var="", env_path=Path("/dev/null"))
        store_merchant_private_key(
            oauth_token, merchant_id, keys.private_key, environment
        )

    return keys


def populate_synvya_profile(merchant_data: dict, keys: NostrKeys) -> Profile:
    """
    Populates a Synvya Profile instance with data retrieved from Square merchant info.

    Args:
        merchant_data (dict): Merchant details from Square API.
        keys (NostrKeys): Merchant NostrKeys for profile creation.

    Returns:
        Profile: A populated Profile instance ready for publishing on Nostr.
    """
    profile = Profile(keys.private_key)

    return profile


# Example usage:
def fetch_and_prepare_profile(
    oauth_token: str, environment: str = "sandbox"
) -> Profile:
    """
    High-level function to fetch merchant info from Square, generate/retrieve
    keys, and prepare a Synvya Profile.

    Args:
        oauth_token (str): OAuth token stored securely in your database.
        environment (str): Square environment to use (default: "sandbox").
    Returns:
        Profile: Populated Synvya Profile instance.
    """
    merchant_info = get_square_merchant_info(oauth_token, environment)
    merchant_id = merchant_info["id"]
    keys = get_or_generate_merchant_keys(oauth_token, merchant_id, environment)
    synvya_profile = populate_synvya_profile(merchant_info, keys)

    return synvya_profile


def create_synvya_private_key_definition(oauth_token: str, environment: str) -> None:
    """
    Creates a custom attribute definition for synvya_private_key using the Square API.

    Args:
        oauth_token (str): OAuth token for authenticating requests.
        environment (str): The environment to use (e.g., "sandbox" or "production").
    """
    headers = {
        "Authorization": f"Bearer {oauth_token}",
        "Square-Version": "2024-04-17",
        "Content-Type": "application/json",
    }

    url = (
        f"{get_square_api_base_url(environment)}/merchants/custom-attribute-definitions"
    )

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

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()

    return response.json()


# Integrate the function into the existing workflow
# Example usage:
# Call this function when the merchant authorizes the app
# create_synvya_private_key_definition(oauth_token, environment)
