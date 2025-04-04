"""Fetch merchant profile from Square and prepare a Synvya Profile."""

from synvya_sdk import Profile

def get_square_merchant_info(oauth_token: str) -> dict:
    """
    Get merchant information from Square.

    Args:
        oauth_token (str): OAuth token for authenticating requests.

    Returns:
        dict: Merchant information.
    """
    ...

def get_merchant_private_key(oauth_token: str, merchant_id: str) -> str | None:
    """
    Fetches the stored merchant private key from Square's Merchant Custom Attributes.

    Args:
        oauth_token (str): OAuth token for authenticating requests.
        merchant_id (str): Square Merchant ID.

    Returns:
        str | None: Private key if exists, otherwise None.
    """
    ...

def store_merchant_private_key(
    oauth_token: str, merchant_id: str, private_key: str
) -> None:
    """
    Stores the merchant's private key as a Merchant Custom Attribute in Square.

    Args:
        oauth_token (str): OAuth token for authenticating requests.
        merchant_id (str): Square Merchant ID.
        private_key (str): The private key to store.
    """
    ...

def get_or_generate_merchant_keys(oauth_token: str, merchant_id: str) -> object:
    """
    Retrieves the merchant's private key stored as a Merchant Custom Attribute.
    If not found, generates new key pair and stores the private key.

    Args:
        oauth_token (str): OAuth token for authenticating requests.
        merchant_id (str): Square Merchant ID.

    Returns:
        object: Merchant's NostrKeys instance with private/public keys.
    """
    ...

def populate_synvya_profile(merchant_data: dict, keys: object) -> Profile:
    """
    Populates a Synvya Profile instance with data retrieved from Square merchant info.

    Args:
        merchant_data (dict): Merchant details from Square API.
        keys (object): Merchant NostrKeys for profile creation.

    Returns:
        Profile: A populated Profile instance ready for publishing on Nostr.
    """
    ...

def fetch_and_prepare_profile(oauth_token: str) -> Profile:
    """
    High-level function to fetch merchant info from Square, generate/retrieve
    keys, and prepare a Synvya Profile.

    Args:
        oauth_token (str): OAuth token stored securely in your database.

    Returns:
        Profile: Populated Synvya Profile instance.
    """
    ...

def create_synvya_private_key_definition(oauth_token: str, environment: str) -> None:
    """
    Creates a custom attribute definition for synvya_private_key using the Square API.

    Args:
        oauth_token (str): OAuth token for authenticating requests.
        environment (str): The environment to use (e.g., "sandbox" or "production").
    """
    ...

def get_square_api_base_url(environment: str) -> str:
    """
    Get the Square API base URL for the given environment.

    Args:
        environment (str): The environment to use (e.g., "sandbox" or "production").

    Returns:
        str: The Square API base URL.
    """
    ...

def get_square_base_url(environment: str) -> str:
    """
    Get the Square base URL for the given environment.

    Args:
        environment (str): The environment to use (e.g., "sandbox" or "production").

    Returns:
        str: The Square base URL.
    """
    ...
