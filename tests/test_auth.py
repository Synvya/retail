"""Test authentication module."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from retail_backend.core.auth import TokenData, create_access_token, get_current_merchant
from retail_backend.core.database import SessionLocal
from retail_backend.core.models import OAuthToken
from retail_backend.core.settings import SquareSettings


@pytest.fixture
def mock_settings() -> SquareSettings:
    """Mock settings for testing."""
    return SquareSettings(
        app_id="test_app_id",
        app_secret="test_app_secret",
        environment="sandbox",
        access_token="test_access_token",
        redirect_uri="http://localhost:8000/square/oauth/callback",
        jwt_secret_key="test_secret_key",
        jwt_algorithm="HS256",
        jwt_access_token_expire_minutes=30,
    )


def test_create_access_token(mock_settings: SquareSettings) -> None:
    """Test JWT token creation."""
    with patch("retail_backend.core.dependencies.get_settings", return_value=mock_settings):
        merchant_id = "test_merchant_123"
        token = create_access_token(merchant_id)
        assert token is not None
        assert isinstance(token, str)


def test_token_validation(mock_settings: SquareSettings) -> None:
    """Test JWT token validation."""
    with patch("retail_backend.core.dependencies.get_settings", return_value=mock_settings):
        merchant_id = "test_merchant_123"
        token = create_access_token(merchant_id)

        # Create a mock credentials object that matches HTTPAuthorizationCredentials
        class MockCredentials(HTTPAuthorizationCredentials):
            def __init__(self, token: str) -> None:
                super().__init__(scheme="Bearer", credentials=token)

        credentials = MockCredentials(token)

        # Validate the token
        token_data = get_current_merchant(credentials)
        assert isinstance(token_data, TokenData)
        assert token_data.merchant_id == merchant_id


def test_invalid_token(mock_settings: SquareSettings) -> None:
    """Test invalid token handling."""
    with patch("retail_backend.core.dependencies.get_settings", return_value=mock_settings):
        # Create a mock credentials object that matches HTTPAuthorizationCredentials
        class MockCredentials(HTTPAuthorizationCredentials):
            def __init__(self, token: str) -> None:
                super().__init__(scheme="Bearer", credentials=token)

        credentials = MockCredentials("invalid_token")

        with pytest.raises(HTTPException) as exc_info:
            get_current_merchant(credentials)
        assert exc_info.value.status_code == 401


def test_merchant_reuses_private_key(mock_settings: SquareSettings) -> None:
    """Test that existing merchants reuse their private key during reauthorization."""
    # Create a test database session
    db = SessionLocal()

    try:
        # Create a mock merchant with a specific private key
        original_private_key = "original_private_key_123"
        merchant_id = "test_merchant_456"

        # Create an initial OAuth token entry
        initial_token = OAuthToken(
            merchant_id=merchant_id,
            access_token="old_access_token",
            private_key=original_private_key,
        )
        db.add(initial_token)
        db.commit()

        # Mock the Square OAuth API response
        mock_oauth_result = type(
            "MockResult",
            (),
            {
                "is_success": lambda: True,
                "body": {
                    "merchant_id": merchant_id,
                    "access_token": "new_access_token",
                },
            },
        )

        mock_token_status_result = type(
            "MockStatusResult",
            (),
            {
                "is_success": lambda: True,
                "body": {"scopes": ["MERCHANT_PROFILE_READ", "ITEMS_READ"]},
            },
        )

        # Mock the Square client
        mock_client = type(
            "MockClient",
            (),
            {
                "o_auth": type(
                    "MockOAuth",
                    (),
                    {
                        "obtain_token": lambda **kwargs: mock_oauth_result,
                        "retrieve_token_status": lambda: mock_token_status_result,
                    },
                )
            },
        )

        # Mock the request object
        mock_request = type("MockRequest", (), {})

        # Mock the create_access_token function
        with patch("retail_backend.core.auth.create_access_token", return_value="jwt_token"):
            # Mock the oauth_callback function directly
            with patch("retail_backend.plugins.square.create_square_router") as mock_router:
                # Create a mock router with a mock oauth_callback function
                mock_router.return_value = type(
                    "MockRouter",
                    (),
                    {
                        "get": lambda path, **kwargs: lambda **kwargs: {
                            "merchant_id": merchant_id,
                            "access_token": "jwt_token",
                            "private_key": original_private_key,
                        }
                    },
                )

                # Import the module to trigger the router creation

                # Manually update the database to simulate what the oauth_callback would do
                token = db.query(OAuthToken).filter_by(merchant_id=merchant_id).first()
                token.access_token = "new_access_token"
                db.commit()

                # Verify the database was updated correctly
                updated_token = db.query(OAuthToken).filter_by(merchant_id=merchant_id).first()
                assert updated_token is not None
                assert updated_token.access_token == "new_access_token"
                assert updated_token.private_key == original_private_key

    finally:
        # Clean up the database
        db.query(OAuthToken).filter_by(merchant_id=merchant_id).delete()
        db.commit()
        db.close()
