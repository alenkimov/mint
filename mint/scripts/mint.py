"""
Mint scripts (invite and other)
"""

from loguru import logger

from ..client import Client


async def try_to_invite(mint_client: Client):
    if mint_client.account.user.invite_id:
        logger.info(f"{mint_client.account} Account already invited. Invite ID: {mint_client.account.user.invite_id}")
        return

    await mint_client.accept_invite()
