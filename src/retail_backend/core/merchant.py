"""Fetch merchant profile from Square and prepare a Synvya Profile."""

import json
import logging

import anyio
from fastapi import HTTPException
from synvya_sdk import NostrClient, NostrKeys, Profile, ProfileType, Stall, StallShippingMethod

from retail_backend.core.models import MerchantProfile
from retail_backend.core.settings import Provider

# Setup module-level logger
logger = logging.getLogger("merchant")

DEFAULT_RELAY = "wss://relay.damus.io"


async def get_nostr_profile(private_key: str) -> MerchantProfile:
    """
    Get merchant Nostr Profile.

    Args:
        private_key (str): The private key of the merchant.

    Returns:
        MerchantProfile: Pydantic model with Nostr Profile data.

    Raises:
        HTTPException: If the merchant Nostr Profile is not found.
    """
    logger.debug("Getting Nostr profile...")

    # Use anyio.to_thread.run_sync to run NostrClient in a separate thread
    def create_client_and_get_profile() -> MerchantProfile:
        client = None
        try:
            # Add validation for private key format
            logger.debug("Creating NostrClient with relay: %s", DEFAULT_RELAY)
            client = NostrClient(DEFAULT_RELAY, private_key=private_key)
            logger.debug("Getting profile from NostrClient")
            profile = client.get_profile()
            logger.debug("Successfully retrieved profile from Nostr")

            # Convert the profile to JSON and then to our MerchantProfile model
            profile_data = json.loads(profile.to_json())
            logger.debug("Profile data: %s.", profile_data)

            # Ensure all string fields have valid string values (not None)
            string_fields = [
                "about",
                "banner",
                "display_name",
                "namespace",
                "picture",
                "public_key",
                "website",
            ]

            for field in string_fields:
                if field in profile_data and profile_data[field] is None:
                    profile_data[field] = ""

            if "nip05" in profile_data and profile_data["nip05"] is None:
                profile_data["nip05"] = profile_data["name"] + "@synvya.com"

            # Ensure hashtags and locations are lists, not None
            if "hashtags" in profile_data and profile_data["hashtags"] is None:
                profile_data["hashtags"] = []
            if "locations" in profile_data and profile_data["locations"] is None:
                profile_data["locations"] = []

            logger.info(
                "Converted Nostr profile to MerchantProfile model. Name: %s.",
                profile_data.get("name", "N/A"),
            )
            return MerchantProfile(**profile_data)
        except RuntimeError as e:
            logger.error("get_nostr_profile - Error: %s: %s.", type(e).__name__, str(e))
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            logger.error(
                "get_nostr_profile - Unexpected Error: %s: %s.",
                type(e).__name__,
                str(e),
            )
            raise HTTPException(status_code=500, detail=f"Server error: {str(e)}") from e
        finally:
            if client:
                logger.debug("Cleaning up NostrClient")
                del client

    # Run the blocking code in a separate thread
    logger.debug("Running NostrClient in a separate thread")
    return await anyio.to_thread.run_sync(create_client_and_get_profile)


async def set_nostr_profile(profile: MerchantProfile, private_key: str) -> None:
    """
    Publishes the Nostr Profile to the Nostr relay

    Args:
        profile (MerchantProfile): Pydantic model with Nostr Profile data.
        private_key (str): Merchant Nostr private key.


    Raises:
        ValueError: If the Nostr Profile data is invalid
    """
    logger.debug("Setting Nostr profile for %s.", profile.name)

    # Use anyio.to_thread.run_sync to run NostrClient in a separate thread
    def create_client_and_set_profile() -> None:
        client = None
        try:
            # Create a NostrClient
            logger.debug("Creating NostrClient with relay: %s.", DEFAULT_RELAY)
            client = NostrClient(DEFAULT_RELAY, private_key=private_key)

            # Derive public key from private key
            logger.debug("Deriving public key from private key")
            public_key = NostrKeys.derive_public_key(private_key)
            logger.debug("Derived public key (first 8 chars): %s...", public_key[:8])

            # Create a synvya_sdk Profile instance from MerchantProfile
            logger.debug("Creating SDK Profile from MerchantProfile")
            sdk_profile = Profile(public_key=public_key)

            # Set fields from MerchantProfile to SDK Profile
            sdk_profile.set_name(profile.name)
            sdk_profile.set_about(profile.about)
            sdk_profile.set_banner(profile.banner)
            sdk_profile.set_bot(profile.bot)
            sdk_profile.set_display_name(profile.display_name)
            sdk_profile.set_namespace(profile.namespace)
            sdk_profile.set_nip05(profile.nip05)
            sdk_profile.set_picture(profile.picture)

            # Convert string profile_type to ProfileType enum
            try:
                logger.debug("Converting profile_type: %s.", profile.profile_type)
                profile_type_enum = ProfileType(profile.profile_type)
            except ValueError:
                # Default to OTHER_OTHER if conversion fails
                logger.warning(
                    "Invalid profile_type: %s. Defaulting to OTHER_OTHER",
                    profile.profile_type,
                )
                profile_type_enum = ProfileType.OTHER_OTHER

            sdk_profile.set_profile_type(profile_type_enum)
            sdk_profile.set_website(profile.website)

            # Add hashtags
            for hashtag in profile.hashtags:
                sdk_profile.add_hashtag(hashtag)

            # Add locations
            for location in profile.locations:
                sdk_profile.add_location(location)

            # Print the profile to be published for debugging
            logger.info("Publishing profile: %s.", sdk_profile.to_json())

            # Set the profile using the SDK
            logger.info("Setting profile using NostrClient")
            client.set_profile(sdk_profile)
            logger.info("Successfully published profile to Nostr")

        except (RuntimeError, ValueError) as e:
            logger.error("Error setting profile: %s: %s.", type(e).__name__, str(e))
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            logger.error("Unexpected error: %s: %s.", type(e).__name__, str(e))
            raise HTTPException(status_code=500, detail=f"Server error: {str(e)}") from e
        finally:
            if client:
                logger.info("Cleaning up NostrClient")
                del client

    # Run the blocking code in a separate thread
    logger.info("Running NostrClient in a separate thread")
    await anyio.to_thread.run_sync(create_client_and_set_profile)


async def set_nostr_stall(provider: Provider, location: dict, private_key: str) -> bool:
    """
    Asynchronously publishes the Nostr Stall to the Nostr relay

    Args:
        provider (Provider): Provider of the location ("square" or "shopify")
        location (dict): Location data
        private_key (str): Merchant Nostr private key.

    Returns:
        bool: True if the Nostr Stall was published successfully, False otherwise.
    """

    if provider == Provider.SQUARE:
        return await anyio.to_thread.run_sync(_set_nostr_stall_square, location, private_key)
    else:
        raise HTTPException(status_code=400, detail="Unsupported provider")


def _set_nostr_stall_square(location: dict, private_key: str) -> bool:
    """
    Internal function to publish the Nostr Stall to the Nostr relay

    TBD: use lat lot to set geohash field of Stall model

    Args:
        stall (Stall): Pydantic model with Nostr Stall data.
        private_key (str): Merchant Nostr private key.

    Returns:
        bool: True if the Nostr Stall was published successfully, False otherwise.
    """

    logger.info("Publishing Nostr stall for %s.", location["name"])

    stall = Stall(
        id=location["id"],
        name=location["name"],
        description=location["description"],
        currency=location["currency"],
        shipping=[
            StallShippingMethod(
                ssm_id=location["id"],
                ssm_cost=0.0,
                ssm_name=location["name"],
                ssm_regions=location["address"]["country"],
            )
        ],
        geohash=None,  # future to convert lat, long to geohash
    )
    try:
        # Create a NostrClient
        client = NostrClient(DEFAULT_RELAY, private_key=private_key)

        client.set_stall(stall)
        logger.info("Successfully published stall to Nostr")
        return True
    except RuntimeError as e:
        logger.error("Error publishing stall to Nostr: %s", e)
        # raise HTTPException(status_code=500, detail=f"Server error: {str(e)}") from e
        return False
    finally:
        if client:
            del client
