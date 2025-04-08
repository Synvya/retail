"""Authentication endpoints."""

from fastapi import APIRouter, Depends

from retail_backend.core.auth import TokenData, create_access_token, get_current_merchant

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token/{merchant_id}")
async def get_token(merchant_id: str) -> dict[str, str]:
    """Create a test token for a merchant.

    WARNING: This endpoint is for testing only and should not be used in production.
    In production, tokens should be created only after proper OAuth authentication.
    """
    token = create_access_token(merchant_id)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me")
async def get_current_user(
    merchant: TokenData = Depends(get_current_merchant),
) -> dict[str, str]:
    """Test endpoint that requires JWT authentication."""
    return {"merchant_id": merchant.merchant_id, "token_expires": str(merchant.exp)}
