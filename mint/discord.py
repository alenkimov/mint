import asyncio
from typing import Any

from loguru import logger
from yarl import URL

from better_proxy import Proxy as BetterProxy

import discord

from .database import DiscordAccount


class DiscordClient(discord.Client):
    # _VERIFY_CHANNEL_ID = 948843667194519607
    # _VERIFY_MESSAGE_ID = 969127174319788092
    # _VERIFY_REACTION = '✅'

    def __init__(self, account: DiscordAccount, proxy: str | BetterProxy, **options):
        self.db_account = account
        options["proxy"] = str(proxy) if proxy else None
        super().__init__(**options)

    async def on_error(self, event_method: str, /, *args: Any, **kwargs: Any) -> None:
        await self.close()
        raise

    async def start(self, *, reconnect: bool = True):
        max_retries = 3  # Set the maximum number of retries
        for attempt in range(max_retries):
            try:
                await super().start(
                    self.gomble.account.discord.auth_token, reconnect=reconnect
                )
                break  # If successful, exit the loop
            except (ValueError, RuntimeError, discord.errors.ConnectionClosed) as e:
                if (
                    "is not a valid HTTPStatus" in str(e)
                    or isinstance(e, RuntimeError)
                    or isinstance(e, discord.errors.ConnectionClosed)
                ):
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)  # Wait before retrying
                        continue  # Retry the request
                    else:
                        raise  # Re-raise the exception after all retries have failed
                else:
                    raise  # Re-raise the exception if it's not related to HTTPStatus
            except discord.errors.LoginFailure:
                self.gomble.account.discord.status = "BAD_TOKEN"
                break

    async def on_ready(self):
        self.gomble.account.discord.status = "GOOD"
        self.gomble.account.discord.id = self.user.id
        self.gomble.account.discord.email = self.user.email
        self.gomble.account.discord.name = self.user.display_name
        self.gomble.account.discord.username = str(self.user)
        self.gomble.account.discord.phone = self.user.phone
        self.gomble.account.discord.required_action = (
            self.required_action and self.required_action.value
        )
        await self.gomble.db_session.commit()

        if self.gomble.account.discord.required_action:
            logger.warning(
                f"{self.gomble.account.discord} {self.gomble.account.discord.required_action}"
            )
            await self.close()
            return

        if not self.user.phone:
            logger.warning(f"{self.gomble.account.discord} No phone number")
            await self.close()
            return

        invite = await self.accept_invite(self.quest.url)
        guild_info = f"{invite.guild.name} guild ({invite.approximate_member_count} members)"
        logger.success(f"{self.gomble.account.discord} {guild_info}: Joined guild")

        self.gomble.account.discord.joined_gomble_guild = "JOINED"

        try:
            await invite.guild.agree_guild_rules(invite)
            logger.success(f"{self.gomble.account.discord} {guild_info}: Accepted rules")
        except discord.errors.HTTPException as exc:
            if exc.code == 150009:
                logger.info(f"{self.gomble.account.discord} {guild_info}: Rules already accepted")
            else:
                raise

        channel = await invite.guild.fetch_channel(self._VERIFY_CHANNEL_ID)
        message = await channel.fetch_message(self._VERIFY_MESSAGE_ID)
        await message.add_reaction(self._VERIFY_REACTION)

        oauth_url = await self.gomble.quest(self.quest.id)
        oauth2_data = dict(URL(oauth_url).query)
        oauth2_data["scopes"] = oauth2_data.pop("scope").split(' ')
        oauth2_data["application_id"] = oauth2_data.pop("client_id")

        try:
            oauth2_location = await self.http.authorize_oauth2(**oauth2_data)
        except discord.errors.DiscordServerError as exc:
            logger.error(exc)
            await self.close()
            return

        location_query = dict(URL(oauth2_location["location"]).query)

        quest_access_token = await self.gomble.request_quest_access_token(
            self.quest.id,
            location_query["code"],
            location_query["state"],
        )
        logger.success(f"{self.gomble.account} {self.gomble.account.discord} Discord bound")

        await self.gomble.complete_quest(self.quest.id, quest_access_token)
        logger.success(f"{self.gomble.account} {self.gomble.account.discord} Квест {self.quest.text} выполнен!")

        await self.gomble.db_session.commit()
        await self.gomble.db_session.refresh(
            self.gomble.account, attribute_names=["discord"]
        )
        await self.close()
