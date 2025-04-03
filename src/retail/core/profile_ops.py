"""Fetch merchant profile from Square and prepare a Synvya Profile."""

from os import getenv
from pathlib import Path

import requests  # type: ignore
from synvya_sdk import NostrKeys, Profile, generate_keys

SQUARE_API_BASE_URL = "https://connect.squareup.com/v2"


def get_square_merchant_info(oauth_token: str) -> dict:
    """
    Retrieves merchant details from the Square API using the provided OAuth token.

    Args:
        oauth_token (str): OAuth token for authenticating requests.

    Returns:
        dict: Merchant details as provided by Square.

    Raises:
        requests.HTTPError: If the API request fails.
    """
    headers = {
        "Authorization": f"Bearer {oauth_token}",
        "Square-Version": "2024-03-20",
        "Content-Type": "application/json",
    }

    url = f"{SQUARE_API_BASE_URL}/merchants/me"

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    return response.json().get("merchant")


def get_merchant_private_key(oauth_token: str, merchant_id: str) -> str | None:
    """
    Fetches the stored merchant private key from Square's Merchant Custom Attributes.

    Args:
        oauth_token (str): OAuth token for authenticating requests.
        merchant_id (str): Square Merchant ID.

    Returns:
        str | None: Private key if exists, otherwise None.
    """
    headers = {
        "Authorization": f"Bearer {oauth_token}",
        "Square-Version": "2024-03-20",
        "Content-Type": "application/json",
    }

    url = f"{SQUARE_API_BASE_URL}/merchants/{merchant_id}/custom-attributes/synvya_private_key"
    response = requests.get(url, headers=headers, timeout=30)

    if response.status_code == 200:
        return response.json().get("custom_attribute", {}).get("value")
    elif response.status_code == 404:
        return None
    else:
        response.raise_for_status()
        return None  # Explicit return to satisfy IDE warnings (will never be executed)


def store_merchant_private_key(oauth_token: str, merchant_id: str, private_key: str):
    """
    Stores the merchant's private key as a Merchant Custom Attribute in Square.

    Args:
        oauth_token (str): OAuth token for authenticating requests.
        merchant_id (str): Square Merchant ID.
        private_key (str): The private key to store.
    """
    headers = {
        "Authorization": f"Bearer {oauth_token}",
        "Square-Version": "2024-03-20",
        "Content-Type": "application/json",
    }

    url = f"{SQUARE_API_BASE_URL}/merchants/{merchant_id}/custom-attributes/synvya_private_key"
    payload = {
        "custom_attribute": {
            "value": private_key,
            "version": 1,
            "visibility": "VISIBILITY_HIDDEN",
        }
    }

    response = requests.put(url, json=payload, headers=headers, timeout=30)
    response.raise_for_status()


def get_or_generate_merchant_keys(oauth_token: str, merchant_id: str) -> NostrKeys:
    """
    Retrieves the merchant's private key stored as a Merchant Custom Attribute.
    If not found, generates new key pair and stores the private key.

    Args:
        oauth_token (str): OAuth token for authenticating requests.
        merchant_id (str): Square Merchant ID.

    Returns:
        NostrKeys: Merchant's NostrKeys instance with private/public keys.
    """
    private_key = get_merchant_private_key(oauth_token, merchant_id)

    if private_key:
        keys = NostrKeys.from_private_key(private_key)
    else:
        keys = generate_keys(env_var="", env_path=Path("/dev/null"))
        store_merchant_private_key(oauth_token, merchant_id, keys.private_key)

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
def fetch_and_prepare_profile(oauth_token: str) -> Profile:
    """
    High-level function to fetch merchant info from Square, generate/retrieve
    keys, and prepare a Synvya Profile.

    Args:
        oauth_token (str): OAuth token stored securely in your database.

    Returns:
        Profile: Populated Synvya Profile instance.
    """
    merchant_info = get_square_merchant_info(oauth_token)
    merchant_id = merchant_info["id"]
    keys = get_or_generate_merchant_keys(oauth_token, merchant_id)
    synvya_profile = populate_synvya_profile(merchant_info, keys)

    return synvya_profile
