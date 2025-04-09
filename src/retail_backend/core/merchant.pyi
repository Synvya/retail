# pylint: disable=missing-docstring,unused-argument
"""Fetch merchant profile from Square and prepare a Synvya Profile."""

from retail_backend.core.models import MerchantProfile

async def get_nostr_profile(private_key: str) -> MerchantProfile: ...
async def set_nostr_profile(profile: MerchantProfile, private_key: str) -> None: ...
