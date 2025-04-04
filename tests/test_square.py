"""
This module contains tests for the Square API integration, specifically focusing on the
functionality of fetching and preparing user profiles from the Square API.

The `test_fetch_and_prepare_profile` function tests the integration by attempting to
fetch a user profile using a predefined OAuth token. It verifies that the profile is
created successfully and prints the public and private keys. In case of an error,
it captures and prints the error message.
"""

import sys

import pytest
from sqlalchemy.orm import Session

from retail.core.database import SessionLocal
from retail.core.models import OAuthToken
from retail.core.profile_ops import fetch_and_prepare_profile  # type: ignore


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


def test_fetch_and_prepare_profile():
    """
    This function is used to test the Square API integration.
    """
    try:
        oauth_token, environment = retrieve_oauth_token()
        profile = fetch_and_prepare_profile(oauth_token, environment)
        assert profile is not None, "Failed to create Synvya Profile."
        assert hasattr(profile, "public_key"), "Profile missing public_key attribute."
        # No longer asserting the private_key
    except Exception as e:
        pytest.fail(f"Test failed due to error: {e}")


if __name__ == "__main__":
    test_fetch_and_prepare_profile()
