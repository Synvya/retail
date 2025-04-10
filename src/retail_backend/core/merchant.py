"""Fetch merchant profile from Square and prepare a Synvya Profile."""

import json
import logging

import anyio
from fastapi import HTTPException
from synvya_sdk import NostrClient, NostrKeys, Profile, ProfileType

from retail_backend.core.models import MerchantProfile

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
    logger.info("Getting Nostr profile...")

    # Use anyio.to_thread.run_sync to run NostrClient in a separate thread
    def create_client_and_get_profile() -> MerchantProfile:
        client = None
        try:
            # Add validation for private key format
            logger.info(f"Creating NostrClient with relay: {DEFAULT_RELAY}")
            client = NostrClient(DEFAULT_RELAY, private_key=private_key)
            logger.info("Getting profile from NostrClient")
            profile = client.get_profile()
            logger.info("Successfully retrieved profile from Nostr")

            # Convert the profile to JSON and then to our MerchantProfile model
            profile_data = json.loads(profile.to_json())
            logger.debug(f"Profile data: {profile_data}")

            # Ensure all string fields have valid string values (not None)
            string_fields = [
                "about",
                "banner",
                "display_name",
                "namespace",
                "nip05",
                "picture",
                "public_key",
                "website",
            ]
            for field in string_fields:
                if field in profile_data and profile_data[field] is None:
                    profile_data[field] = ""

            # Ensure hashtags and locations are lists, not None
            if "hashtags" in profile_data and profile_data["hashtags"] is None:
                profile_data["hashtags"] = []
            if "locations" in profile_data and profile_data["locations"] is None:
                profile_data["locations"] = []

            logger.info(
                f"Converted Nostr profile to MerchantProfile model. Name: {profile_data.get('name', 'N/A')}"
            )
            return MerchantProfile(**profile_data)
        except RuntimeError as e:
            logger.error(f"get_nostr_profile - Error: {type(e).__name__}: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"get_nostr_profile - Unexpected error: {type(e).__name__}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
        finally:
            if client:
                logger.info("Cleaning up NostrClient")
                del client

    # Run the blocking code in a separate thread
    logger.info("Running NostrClient in a separate thread")
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
    logger.info(f"Setting Nostr profile for {profile.name}")

    # Use anyio.to_thread.run_sync to run NostrClient in a separate thread
    def create_client_and_set_profile() -> None:
        client = None
        try:
            # Create a NostrClient
            logger.info(f"Creating NostrClient with relay: {DEFAULT_RELAY}")
            client = NostrClient(DEFAULT_RELAY, private_key=private_key)

            # Derive public key from private key
            logger.info("Deriving public key from private key")
            public_key = NostrKeys.derive_public_key(private_key)
            logger.info(f"Derived public key (first 8 chars): {public_key[:8]}...")

            # Create a synvya_sdk Profile instance from MerchantProfile
            logger.info("Creating SDK Profile from MerchantProfile")
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
                logger.info(f"Converting profile_type: {profile.profile_type}")
                profile_type_enum = ProfileType(profile.profile_type)
            except ValueError:
                # Default to OTHER_OTHER if conversion fails
                logger.warning(
                    f"Invalid profile_type: {profile.profile_type}. Defaulting to OTHER_OTHER"
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
            logger.info(f"Publishing profile: {sdk_profile.to_json()}")

            # Set the profile using the SDK
            logger.info("Setting profile using NostrClient")
            client.set_profile(sdk_profile)
            logger.info("Successfully published profile to Nostr")

        except (RuntimeError, ValueError) as e:
            logger.error(f"Error setting profile: {type(e).__name__}: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            logger.error(f"Unexpected error: {type(e).__name__}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
        finally:
            if client:
                logger.info("Cleaning up NostrClient")
                del client

    # Run the blocking code in a separate thread
    logger.info("Running NostrClient in a separate thread")
    await anyio.to_thread.run_sync(create_client_and_set_profile)
