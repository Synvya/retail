"""Authentication module for JWT handling."""

from datetime import UTC, datetime, timedelta
from typing import Any, Optional, cast

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from retail.core.dependencies import get_settings
from retail.core.settings import Provider, SquareSettings

security = HTTPBearer()


class TokenData(BaseModel):
    """Token data model."""

    merchant_id: str
    exp: Optional[datetime] = None


def create_access_token(merchant_id: str) -> str:
    """Create a new JWT access token."""
    settings = cast(SquareSettings, get_settings(Provider.SQUARE))
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    to_encode = {"merchant_id": merchant_id, "exp": expire}
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def get_current_merchant(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenData:
    """Validate JWT token and return merchant data."""
    settings = cast(SquareSettings, get_settings(Provider.SQUARE))
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        merchant_id_value: Any | None = payload.get("merchant_id")
        if not isinstance(merchant_id_value, str):
            raise credentials_exception
        merchant_id: str = merchant_id_value

        exp_value = payload.get("exp")
        if exp_value is None:
            raise credentials_exception

        token_data = TokenData(
            merchant_id=merchant_id, exp=datetime.fromtimestamp(exp_value, tz=UTC)
        )

        if token_data.exp is None or token_data.exp < datetime.now(UTC):
            raise credentials_exception

        return token_data
    except JWTError:
        raise credentials_exception
