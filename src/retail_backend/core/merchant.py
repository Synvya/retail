"""Fetch merchant profile from Square and prepare a Synvya Profile."""

import json
import logging

import anyio
from fastapi import HTTPException
from synvya_sdk import (
    NostrClient,
    NostrKeys,
    Product,
    ProductShippingCost,
    Profile,
    ProfileType,
    Stall,
    StallShippingMethod,
)

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
    def _get_nostr_profile() -> MerchantProfile:
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

            logger.debug("_get_nostr_profile: NIP05: %s", profile_data["nip05"])

            # Ensure hashtags and locations are lists, not None
            if "hashtags" in profile_data and profile_data["hashtags"] is None:
                profile_data["hashtags"] = []
            if "locations" in profile_data and profile_data["locations"] is None:
                profile_data["locations"] = []

            logger.debug(
                "Converted Nostr profile to MerchantProfile model. Name: %s.",
                profile_data.get("name", "N/A"),
            )
            return MerchantProfile(**profile_data)
        except RuntimeError as e:
            logger.error("_get_nostr_profile - Error: %s: %s.", type(e).__name__, str(e))
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            logger.error(
                "_get_nostr_profile - Unexpected Error: %s: %s.",
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
    return await anyio.to_thread.run_sync(_get_nostr_profile)


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
    def _set_nostr_profile() -> None:
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
            sdk_profile.set_picture(profile.picture)

            if profile.nip05 == "":
                profile.nip05 = profile.name + "@synvya.com"
            sdk_profile.set_nip05(profile.nip05)
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
            logger.debug("Publishing profile: %s.", sdk_profile.to_json())

            # Set the profile using the SDK
            logger.debug("Setting profile using NostrClient")
            client.set_profile(sdk_profile)
            logger.debug("Successfully published profile to Nostr")

        except (RuntimeError, ValueError) as e:
            logger.error("Error setting profile: %s: %s.", type(e).__name__, str(e))
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            logger.error("Unexpected error: %s: %s.", type(e).__name__, str(e))
            raise HTTPException(status_code=500, detail=f"Server error: {str(e)}") from e
        finally:
            if client:
                logger.debug("Cleaning up NostrClient")
                del client

    # Run the blocking code in a separate thread
    logger.debug("Running NostrClient in a separate thread")
    await anyio.to_thread.run_sync(_set_nostr_profile)


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


async def set_nostr_products(
    provider: Provider,
    products: list[dict],
    categories: list[dict],
    images: list[dict],
    private_key: str,
) -> dict:
    """
    Asynchronously publishes the Nostr Product to the Nostr relay

    Args:
        provider (Provider): Provider of the product ("square" or "shopify")
        products (list[dict]): List of products
        categories (list[dict]): List of categories
        images (list[dict]): List of images
        private_key (str): Merchant Nostr private key.

    Returns:
        dict:
        {
            "products_published": int,
            "products_failed": int,
        }
    """
    if provider == Provider.SQUARE:
        return await anyio.to_thread.run_sync(
            _set_nostr_products_square, products, categories, images, private_key
        )
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

    logger.debug("Publishing Nostr stall for %s.", location["name"])

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
                ssm_regions=[location["address"]["country"]],
            )
        ],
        geohash="",  # future to convert lat, long to geohash
    )
    try:
        # Create a NostrClient
        client = NostrClient(DEFAULT_RELAY, private_key=private_key)

        client.set_stall(stall)
        logger.debug("Successfully published stall to Nostr")
        return True
    except RuntimeError as e:
        logger.error("Error publishing stall to Nostr: %s", e)
        return False
    finally:
        if client:
            del client


def _set_nostr_products_square(
    products: list[dict], categories: list[dict], images: list[dict], private_key: str
) -> dict:
    """
    Internal function to publish the Nostr Product to the Nostr relay

    Args:
        products (list[dict]): List of products
        categories (list[dict]): List of categories
        images (list[dict]): List of images
        private_key (str): Merchant Nostr private key.

    Returns:
        dict:
        {
            "products_published": int,
            "products_failed": int,
        }
    """
    try:
        client = NostrClient(DEFAULT_RELAY, private_key=private_key)
        stalls = client.get_stalls(NostrKeys.derive_public_key(private_key))
        if not stalls:
            logger.error("No stalls found for merchant.")
            if client:
                del client
            return {"products_published": 0, "products_failed": len(products)}
    except RuntimeError as e:
        logger.error("Error getting stalls: %s", e)
        if client:
            del client
        logger.error("Error creating the Nostr client: %s", e)
        return {"products_published": 0, "products_failed": len(products)}

    products_published = 0
    products_failed = 0

    nostr_products: list[Product] = []

    for product in products:
        product_image_ids = set(product["item_data"]["image_ids"])
        product_images = [
            image["image_data"]["url"] for image in images if image["id"] in product_image_ids
        ]

        product_category_ids = {cat["id"] for cat in product["item_data"]["categories"]}

        product_categories = [
            category["category_data"]["name"]
            for category in categories
            if category["id"] in product_category_ids
        ]

        nostr_product = Product(
            id=product["id"],
            stall_id=stalls[0].id,
            name=product["item_data"]["name"],
            description=product["item_data"]["description"],
            images=product_images,
            currency=product["item_data"]["variations"][0]["item_variation_data"]["price_money"][
                "currency"
            ],
            price=product["item_data"]["variations"][0]["item_variation_data"]["price_money"][
                "amount"
            ]
            / 100,
            quantity=100,
            shipping=[
                ProductShippingCost(
                    psc_id=stalls[0].id,
                    psc_cost=0.0,
                )
            ],
            categories=product_categories,
            specs=[],
            seller=NostrKeys.derive_public_key(private_key),
        )
        nostr_products.append(nostr_product)

    for nostr_product in nostr_products:
        try:
            result = client.set_product(nostr_product)
            if result:
                products_published += 1
            else:
                products_failed += 1
        except RuntimeError as e:
            products_failed += 1
            logger.error("Error publishing Square catalog product: %s", str(e))
        except Exception as e:
            logger.error("Unexpected error: %s: %s.", type(e).__name__, str(e))
            products_failed += 1

    if client:
        del client

    return {"products_published": products_published, "products_failed": products_failed}
