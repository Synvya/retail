"""
This module contains tests for the Square API integration, specifically focusing on the
functionality of fetching and preparing user profiles from the Square API.

The `test_fetch_and_prepare_profile` function tests the integration by attempting to
fetch a user profile using a predefined OAuth token. It verifies that the profile is
created successfully and prints the public and private keys. In case of an error,
it captures and prints the error message.
"""

import pytest
from sqlalchemy.orm import Session
from square.client import Client  # type: ignore

from retail.core.database import SessionLocal
from retail.core.dependencies import get_square_client
from retail.core.models import OAuthToken
from retail.plugins.square import (
    get_merchant_info,
    get_merchant_private_key,
    populate_synvya_profile,
)


@pytest.fixture(scope="session", name="client")
def client_fixture() -> Client:
    """
    Fixture to get the Square client.
    """
    return get_square_client()


def retrieve_oauth_token() -> tuple[str, str]:
    """
    Retrieves the OAuth token securely from the database.
    Args:
        None
    Returns:
        tuple[str, str]: A tuple containing the access token and the environment.
    Raises:
        RuntimeError: If the OAuth token is not found in the database.
    """
    db: Session = SessionLocal()
    try:
        token_entry = db.query(OAuthToken).filter_by(environment="sandbox").first()
        if token_entry:
            return str(token_entry.access_token), str(token_entry.environment)
        else:
            raise RuntimeError("OAuth token not found in the database.")
    finally:
        db.close()


def test_get_merchant_info(client: Client):
    """
    Test get_merchant_info.
    """
    merchant_info = get_merchant_info(client)
    assert merchant_info is not None, "Failed to get merchant info."


def test_get_merchant_private_key(client: Client):
    """
    Test get_merchant_private_key.
    """
    merchant_info = get_merchant_info(client)
    merchant_id = merchant_info["id"]
    private_key = get_merchant_private_key(merchant_id, client)
    assert private_key is not None, "Failed to get merchant private key."


def test_populate_synvya_profile(client: Client):
    """
    Test populate_synvya_profile.
    """
    merchant_info = get_merchant_info(client)
    merchant_id = merchant_info["id"]
    private_key = get_merchant_private_key(merchant_id, client)
    assert private_key is not None, "Failed to get merchant private key."
    profile = populate_synvya_profile(merchant_info, private_key)
    assert profile is not None, "Failed to populate Synvya profile."
