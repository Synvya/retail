"""Fetch merchant profile from Square and prepare a Synvya Profile."""

import json

import anyio
from fastapi import HTTPException
from synvya_sdk import NostrClient, NostrKeys, Profile, ProfileType

from retail_backend.core.models import MerchantProfile

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

    # Use anyio.to_thread.run_sync to run NostrClient in a separate thread
    def create_client_and_get_profile() -> MerchantProfile:
        client = None
        try:
            # Add validation for private key format

            client = NostrClient(DEFAULT_RELAY, private_key=private_key)
            profile = client.get_profile()
            # Convert the profile to JSON and then to our MerchantProfile model
            profile_data = json.loads(profile.to_json())

            # Ensure all string fields have valid string values (not None)
            string_fields = [
                "about",
                "banner",
                "display_name",
                "namespace",
                "nip05",
                "picture",
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

            return MerchantProfile(**profile_data)
        except RuntimeError as e:
            print(f"get_nostr_profile - Error: {type(e).__name__}: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            print(f"get_nostr_profile - Unexpected error: {type(e).__name__}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
        finally:
            if client:
                del client

    # Run the blocking code in a separate thread
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

    # Use anyio.to_thread.run_sync to run NostrClient in a separate thread
    def create_client_and_set_profile() -> None:
        client = None
        try:
            # Create a NostrClient
            client = NostrClient(DEFAULT_RELAY, private_key=private_key)

            # Derive public key from private key
            public_key = NostrKeys.derive_public_key(private_key)

            # Create a synvya_sdk Profile instance from MerchantProfile
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
                profile_type_enum = ProfileType(profile.profile_type)
            except ValueError:
                # Default to OTHER_OTHER if conversion fails
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
            # print(f"Publishing profile: {sdk_profile.to_json()}")

            # Set the profile using the SDK
            client.set_profile(sdk_profile)

        except (RuntimeError, ValueError) as e:
            print(f"Error setting profile: {type(e).__name__}: {str(e)}")
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            print(f"Unexpected error: {type(e).__name__}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")
        finally:
            if client:
                del client

    # Run the blocking code in a separate thread
    await anyio.to_thread.run_sync(create_client_and_set_profile)
