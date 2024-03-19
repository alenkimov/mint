"""
Mint scripts (invite and other)
"""

from loguru import logger

from ..client import Client


async def try_to_invite(mint_client: Client):
    mint_account = mint_client.account
    mint_user = mint_account.user
    if not mint_user:
        logger.warning(f"{mint_account} Информация о пользователе не запрошена (отсутствует в бд)")
        return

    if mint_user.invite_id:
        logger.info(f"{mint_client.account} Account already invited. Invite ID: {mint_client.account.user.invite_id}")
        return

    await mint_client.accept_invite()
