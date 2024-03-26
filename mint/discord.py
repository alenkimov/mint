from typing import Any

from loguru import logger
from yarl import URL

from better_proxy import Proxy as BetterProxy

import discord

from .errors import BadDiscordAccount
from .database import AsyncSessionmaker, DiscordAccount, DiscordGuildJoinStatus, update_or_create


class DiscordClient(discord.Client):
    def __init__(
            self,
            account: DiscordAccount,
            proxy: str | BetterProxy = None,
            *,
            oauth2_data: dict,
            invite_code_or_url: str,
            verify_reaction: str = None,
            verify_message_id: int = None,
            verify_channel_id: int = None,
            **options,
    ):
        self.db_account = account
        self.auth_code = None
        self.oauth2_data = oauth2_data
        self.invite_code_or_url = invite_code_or_url
        self.verify_reaction = verify_reaction
        self.verify_message_id = verify_message_id
        self.verify_channel_id = verify_channel_id
        options["proxy"] = str(proxy) if proxy else None
        super().__init__(**options)

    async def on_error(self, event_method: str, /, *args: Any, **kwargs: Any) -> None:
        await self.close()
        raise

    # async def start(self, *, reconnect: bool = True):
    #     max_retries = 3  # Set the maximum number of retries
    #     for attempt in range(max_retries):
    #         try:
    #             await super().start(
    #                 self.db_account.auth_token, reconnect=reconnect
    #             )
    #             break  # If successful, exit the loop
    #         except (ValueError, RuntimeError, discord.errors.ConnectionClosed) as e:
    #             if (
    #                 "is not a valid HTTPStatus" in str(e)
    #                 or isinstance(e, RuntimeError)
    #                 or isinstance(e, discord.errors.ConnectionClosed)
    #             ):
    #                 if attempt < max_retries - 1:
    #                     await asyncio.sleep(1)  # Wait before retrying
    #                     continue  # Retry the request
    #                 else:
    #                     raise  # Re-raise the exception after all retries have failed
    #             else:
    #                 raise  # Re-raise the exception if it's not related to HTTPStatus
    #         except discord.errors.LoginFailure:
    #             self.db_account.status = "BAD_TOKEN"
    #             raise BadDiscordAccount(self.db_account, f"Bad Discord token")

    async def on_ready(self):
        async with AsyncSessionmaker() as session:
            session.add(self.db_account)

            self.db_account.status = "GOOD"
            self.db_account.id = self.user.id
            self.db_account.email = self.user.email
            self.db_account.name = self.user.display_name
            self.db_account.username = str(self.user)
            self.db_account.phone = self.user.phone
            if self.required_action:
                self.db_account.required_action = self.required_action.value
            await session.commit()

            if self.db_account.required_action:
                await self.close()
                raise BadDiscordAccount(self.db_account, f"Required action: {self.db_account.required_action}")

            if not self.db_account.phone:
                await self.close()
                raise BadDiscordAccount(self.db_account, f"No phone number")

            invite = await self.accept_invite(self.invite_code_or_url)
            guild_info = f"{invite.guild.name} guild ({invite.approximate_member_count} members)"
            logger.success(f"{self.db_account} {guild_info}: Joined guild")

            await update_or_create(
                session,
                DiscordGuildJoinStatus,
                {
                    "discord_account": self.db_account,
                    "guild_id": invite.guild.id,
                    "invite_code": invite.code,
                    "joined": True,
                },
                discord_account=self.db_account,
                guild_id=invite.guild.id,
            )

            await session.commit()

            try:
                await invite.guild.agree_guild_rules(invite)
                logger.success(f"{self.db_account} {guild_info}: Accepted rules")
            except discord.errors.HTTPException as exc:
                if exc.code == 150009:
                    logger.info(f"{self.db_account} {guild_info}: Rules already accepted")
                else:
                    raise

        if self.verify_channel_id and self.verify_message_id and self.verify_reaction:
            channel = await invite.guild.fetch_channel(self.verify_channel_id)
            message = await channel.fetch_message(self.verify_message_id)
            await message.add_reaction(self.verify_reaction)

        # TODO Повторная попытка на discord.errors.DiscordServerError
        oauth2_location = await self.http.authorize_oauth2(**self.oauth2_data)

        location_query = dict(URL(oauth2_location["location"]).query)
        self.auth_code = location_query["code"]
        await self.close()


async def join_guild_and_make_oauth2(
            account: DiscordAccount,
            proxy: str | BetterProxy,
            *,
            oauth2_data: dict,
            invite_code_or_url: str,
            verify_reaction: str = None,
            verify_message_id: int = None,
            verify_channel_id: int = None,
    ) -> str:
    """
    :return: auth_code
    """
    client = DiscordClient(
        account,
        proxy,
        oauth2_data=oauth2_data,
        invite_code_or_url=invite_code_or_url,
        verify_reaction=verify_reaction,
        verify_message_id=verify_message_id,
        verify_channel_id=verify_channel_id,
    )
    await client.start(account.auth_token)
    return client.auth_code
