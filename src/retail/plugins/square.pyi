"""Square plugin module."""

from fastapi import APIRouter
from sqlalchemy.orm import Session
from square.client import Client  # type: ignore
from synvya_sdk import Profile

from retail.core.settings import SquareSettings

router: APIRouter

def get_db() -> Session: ...
def create_square_router(
    client: Client,
    settings: SquareSettings,
    square_base_url: str,
    square_api_url: str,
) -> APIRouter: ...
def get_merchant_info(client: Client) -> dict: ...
def get_merchant_private_key(merchant_id: str, client: Client) -> str | None: ...
def store_merchant_private_key(
    merchant_id: str, private_key: str, client: Client
) -> None: ...
def create_private_key_attribute(
    settings: SquareSettings,
    square_api_url: str,
) -> None: ...
def populate_synvya_profile(merchant_data: dict, private_key: str) -> Profile: ...
