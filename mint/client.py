import asyncio
from functools import wraps
import random

from loguru import logger
from better_web3.utils import sign_message
from eth_utils import to_wei
from eth_account.account import LocalAccount
import web3

from .database import AsyncSessionmaker, MintAccount, MintUser, update_or_create
from .api.http import HTTPClient
from .api.errors import HTTPException
from .api.models import Task
from .twitter import TwitterClient
from .discord import join_guild_and_make_oauth2
from .errors import TwitterScriptError
from .onchain.scripts import request_balances, wait_fot_tx_receipt
from .onchain.chains import sepolia, mintchain
from .onchain.contracts import eth_to_mintchain_bridge
from .config import CONFIG

TWITTER_OAUTH2_PARAMS = {
    'state': 'mintchain',
    'code_challenge_method': 'plain',
    'code_challenge': 'mintchain',
    'client_id': 'enpfUjhndkdrdHhld29aTW96eGM6MTpjaQ',
    'scope': 'tweet.read users.read follows.read offline.access',
    'response_type': 'code',
    'redirect_uri': 'https://www.mintchain.io/mint-forest',
}
DISCORD_OAUTH2_DATA = {
    "application_id": 1214172619339735071,
    "response_type": "code",
    "redirect_uri": "https://www.mintchain.io/mint-forest",
    "scopes": ["identify", "guilds", "guilds.members.read"],
}
DISCORD_MINTCHAIN_GUILD_INVITE_CODE = "mint-blockchain"
DISCORD_MINTCHAIN_GUILD_ID = 1172040134355587092
DISCORD_MINTCHAIN_GUILD_VERIFY_CHANNEL_ID = 1181968185206001726
DISCORD_MINTCHAIN_GUILD_VERIFY_MESSAGE_ID = 1181968186879516744
DISCORD_MINTCHAIN_GUILD_VERIFY_REACTION = '✅'

TASK_IDS_TO_IGNORE = {6, }


class Client:
    def __init__(self, account: MintAccount):
        self._account = None
        self.http = HTTPClient()
        self.account = account

    @property
    def account(self) -> MintAccount:
        return self._account

    @account.setter
    def account(self, account: MintAccount):
        self._account = account
        self.http.auth_token = account.auth_token

        if self.account.proxy:
            self.http._session.proxy = account.proxy.better_proxy

    async def relogin(self) -> bool:
        """
        :return: Interacted (Logged in or not)
        """
        nonce = random.randint(1_000_000, 9_999_999)
        message = (f"You are participating in the Mint Forest event: "
                   f"\n {self.account.wallet.eth_account.address}"
                   f"\n\nNonce: {nonce}")
        signature = sign_message(message, self.account.wallet.eth_account)
        # Нужно передавать именно ChecksumAddress
        user = await self.http.login(self.account.wallet.eth_account.address, message, f"0x{signature}")
        logger.success(f"{self.account} Logged in")

        # Сохраняем информацию об аккаунте в БД
        async with AsyncSessionmaker() as session:
            session.add(self.account)
            self.account.auth_token = self.http.auth_token
            self.account.user, _ = await update_or_create(
                session,
                MintUser,
                user.model_dump(exclude={"signs"}),
                id=user.id,
            )
            await session.commit()

        return True

    async def login(self) -> bool:
        """
        :return: Interacted (Logged in or not)
        """
        if self.account.auth_token:
            logger.info(f"{self.account} Using saved auth_token")
            return False

        return await self.relogin()

    @staticmethod
    def relogin_on_error(method):
        @wraps(method)
        async def wrapper(self, *args, **kwargs):
            # return await method(self, *args, **kwargs)
            try:
                return await method(self, *args, **kwargs)
            except HTTPException as exc:
                if not exc.message == "Authentication failed":
                    raise

                await self.relogin()
                return await method(self, *args, **kwargs)

        return wrapper

    @relogin_on_error
    async def try_to_bind_discord(self) -> bool:
        """
        :return: Interacted (Bound or not)
        """
        if not self.account.discord_account:
            return False

        async with AsyncSessionmaker() as session:
            session.add(self.account)
            await session.refresh(self.account.discord_account, attribute_names=["mint_user"])

            if self.account.discord_account.mint_user:
                # Проверка на привязку
                if self.account.mint_user_id == self.account.discord_account.mint_user.id:
                    logger.info(f"{self.account} {self.account.discord_account}"
                                f" Discord account already bound")
                    return False
                else:
                    pass

            joined_mint_guild = await self.account.discord_account.joined_guild(session, DISCORD_MINTCHAIN_GUILD_ID)

            # Если возвращает None, значит войти в гильдию еще не пробовали
            if joined_mint_guild is None:
                pass

            # Если возвращает False, значит попытка войти в гильдию увенчалась неудачей,
            # что, скорее всего, означает то, что войти не получится вовсе и не стоит больше пытаться
            if joined_mint_guild is False:
                logger.warning(f"{self.account.discord_account}"
                               f" Joining Mint Discord guild failed before")
                return False

        if self.account.discord_account.required_action:
            logger.warning(f"{self.account.discord_account}"
                           f" Required action: {self.account.discord_account.required_action}")
            return False

        if self.account.discord_account.id and not self.account.discord_account.phone:
            logger.warning(f"{self.account.discord_account}"
                           f" No phone number")
            return False

        try:
            auth_code = await join_guild_and_make_oauth2(
                self.account.discord_account,
                self.account.proxy.better_proxy if self.account.proxy else None,
                oauth2_data=DISCORD_OAUTH2_DATA,
                invite_code_or_url=DISCORD_MINTCHAIN_GUILD_INVITE_CODE,
                verify_reaction=DISCORD_MINTCHAIN_GUILD_VERIFY_REACTION,
                verify_message_id=DISCORD_MINTCHAIN_GUILD_VERIFY_MESSAGE_ID,
                verify_channel_id=DISCORD_MINTCHAIN_GUILD_VERIFY_CHANNEL_ID,
            )
        except ValueError as exc:
            logger.warning(f"{self.account} {self.account.discord_account} {exc}")
            return False

        try:
            await self.http.bind_discord(auth_code)
        except HTTPException as exc:
            if not exc.message == "Discord has already been bound":
                raise
        logger.success(f"{self.account} {self.account.discord_account} Discord bound!")
        # Так как метод привязки Discord не возвращает id привязанного Discord аккаунта,
        #   запрашиваем данные о пользователе снова
        await self.request_self()
        return True

    @relogin_on_error
    async def try_to_accept_invite(self) -> bool:
        """
        :return: Interacted (Invited or not)
        """
        # Если у аккаунта уже есть инвайтер, то пропускаем его
        if self.account.user.inviter_user_id:
            logger.info(f"{self.account} Account already invited."
                        f"\n\tInviter user ID: {self.account.user.inviter_user_id}")
            return False

        self.account.user.inviter_user_id = await self.http.accept_invite(self.account.invite_code)
        logger.success(f"{self.account} Account invited!"
                       f"\n\tInviter user ID: {self.account.user.inviter_user_id}"
                       f"\n\tInvite code: {self.account.invite_code}")

        # Сохраняем состояние аккаунта в БД
        async with AsyncSessionmaker() as session:
            session.add(self.account)
            await session.commit()

        return True

    @relogin_on_error
    async def claim_energy(self) -> bool:
        """
        :return: Interacted (Claimed or not)
        """
        claimed = False

        energy_list = await self.http.request_energy_list()
        for energy in energy_list:
            if not energy.freeze:
                claimed_me = await self.http.claim_energy(id=f"{energy.amount}_", **energy.model_dump())
                logger.success(f"{self.account} Claimed {claimed_me} energy")
                claimed = True

        assets = await self.http.request_assets()
        for asset in assets:
            if not asset.type == "energy":
                continue

            claimed_me = await self.http.open_box(asset.id)
            logger.success(f"{self.account} Box claimed! Claimed {claimed_me} energy")
            claimed = True

        await self.request_self()
        return claimed

    @relogin_on_error
    async def complete_tasks(self) -> bool:
        """
        :return: Interacted (Tasks completed or not)
        """
        interacted = False

        tasks = await self.http.request_task_list()
        unclaimed_tasks: list[Task] = [task for task in tasks if not task.claimed]

        proxy = None
        if self.account.proxy:
            proxy = self.account.proxy.better_proxy

        for task in unclaimed_tasks:
            if task.id == 1:
                async with TwitterClient(self.account.twitter_account, proxy=proxy) as twitter_client:  # type: TwitterClient
                    await twitter_client.follow("1643440230903730176")
                claimed_me = await self.http.sumbit_task(task.id)
                interacted = True
                logger.success(f"{self.account} Task '{task.name}' completed! Claimed {claimed_me} energy")

            elif task.id == 3:
                async with TwitterClient(self.account.twitter_account, proxy=proxy) as twitter_client:  # type: TwitterClient
                    text = """I'm collecting @Mint_Blockchain's ME $MINT in the #MintForest🌳!

Mint is the L2 for NFT industry, powered by @nftscan_com and @Optimism.

Join Mint Forest here: https://mintchain.io/mint-forest 

#MintBlockchain #L2forNFT"""
                    tweet = await twitter_client.tweet(text)
                claimed_me = await self.http.sumbit_task(task.id, twitter_url=tweet.url)
                interacted = True
                logger.success(f"{self.account} Task '{task.name}' completed! Claimed {claimed_me} energy")

            elif task.id == 5:  # Testnet Bridge task
                sepolia_balance, mintchain_balance_wei = await request_balances(self.account)
                wallet: LocalAccount = self.account.wallet.eth_account

                if not sepolia_balance:
                    logger.warning(f"{self.account} [{wallet.address}]"
                                   f" No {sepolia.name} ${sepolia.native_currency.symbol} balance.")
                    continue

                if not mintchain_balance_wei:
                    logger.info(f"{self.account} [{wallet.address}] Bridging...")
                    try:
                        eth_to_mintchain_bridge_amount = to_wei(random.uniform(*CONFIG.BRIDGE.SEPOLIA_ETH_BRIDGE_AMOUNT_RANGE), 'ether')
                        tx_hash = await eth_to_mintchain_bridge.bridge(wallet, eth_to_mintchain_bridge_amount)
                        await wait_fot_tx_receipt(sepolia, self.account, tx_hash, value=eth_to_mintchain_bridge_amount)

                    except (ValueError, web3.exceptions.TimeExhausted) as exc:
                        logger.error(f"{self.account} [{wallet.address}] Failed to bridge: {exc}")
                        continue

                    # mintchain_to_eth_bridge_amount = to_wei(random.uniform(*CONFIG.BRIDGE.MINTCHAIN_ETH_BRIDGE_AMOUNT_RANGE), 'ether')
                    # tx_hash = await mintchain_to_eth_bridge.bridge(wallet, mintchain_to_eth_bridge_amount)
                    # await wait_fot_tx_receipt(mintchain, self.account, tx_hash, value=eth_to_mintchain_bridge_amount)

                    while not mintchain_balance_wei:
                        sleep_time = 30  # sec.
                        logger.info(
                            f"{self.account} [{wallet.address}]"
                            f" No {mintchain.name} ${mintchain.native_currency.symbol} balance."
                            f" Sleeping {sleep_time} sec...")
                        await asyncio.sleep(sleep_time)
                        sepolia_balance_wei, mintchain_balance_wei = await request_balances(self.account)

                claimed_me = await self.http.sumbit_task(task.id)
                interacted = True
                logger.success(f"{self.account} Task '{task.name}' completed! Claimed {claimed_me} energy")

            elif task.id == 2:  # Discord bind task
                if not self.account.discord_account:
                    continue

                if not self.account.discord_account.id:
                    logger.warning(f"{self.account}"
                                   f" Информация о Discord аккаунте этого Mint аккаунта не запрошена")
                    continue

                async with AsyncSessionmaker() as session:
                    session.add(self.account)
                    await session.refresh(self.account.discord_account, attribute_names=["mint_user"])

                if not self.account.discord_account.mint_user:
                    logger.warning(f"{self.account.discord_account}"
                                   f" Ни к одному из запрошенных Mint аккаунтов не привязан этот Discord аккаунт")
                    continue

                # TODO Проверка на нахождение на сервере

                claimed_me = await self.http.submit_discord_task()
                interacted = True
                logger.success(f"{self.account} Task '{task.name}' completed! Claimed {claimed_me} energy")

            elif task.id in TASK_IDS_TO_IGNORE:
                pass

            else:
                logger.warning(f"{self.account} Can't complete task '{task.name}'")

        return interacted

    @relogin_on_error
    async def request_self(self):
        user = await self.http.request_self()
        logger.info(f"{self.account} User data requested")

        # Сохраняем информацию о пользователе в БД
        async with AsyncSessionmaker() as session:
            session.add(self.account)
            # По сути это как update из Django ORM
            # Здесь нет смысла делать update_or_create, так как аккаунт уже создан и запрошен на моменте логина
            for key, value in user.model_dump().items():
                setattr(self.account.user, key, value)
            await session.commit()

    @relogin_on_error
    async def inject_all(self) -> bool:
        """
        :return: Interacted (Injected or not)
        """
        if not self.account.user.me:
            return False

        await self.http.inject(self.account.user.me, self.account.wallet.address)
        logger.success(f"{self.account} Injected {self.account.user.me} ME")
        await self.request_self()
        return True

    @relogin_on_error
    async def try_to_verify_wallet(self) -> bool:
        """
        :return: Interacted (Verified or not)
        """
        if self.account.user.status == "verified":
            return False

        try:
            await self.http.verify_wallet()
        except HTTPException as exc:
            if exc.message == "Unfortunately, you did not pass our verification process.":
                # Если кошелек не прошел проверку, сохраняем информацию об этом
                self.account.wallet.verification_failed = True
                async with AsyncSessionmaker() as session:
                    session.add(self.account)
                    await session.commit()
                raise

            elif exc.message == "Wallet was registed, please login again":
                logger.info(f"{self.account} {self.account.wallet.address} Wallet already verified.")
                interacted = await self.relogin()
                await self.request_self()
                return interacted
            else:
                raise

        logger.success(f"{self.account} {self.account.wallet.address} Wallet verified!")
        return True

    @relogin_on_error
    async def try_to_bind_twitter(self) -> bool:

        # Запрашиваем у БД все требуемые для работы данные
        async with AsyncSessionmaker() as session:
            session.add(self.account)
            await session.refresh(self.account, attribute_names=["twitter_account"])
            await session.refresh(self.account.twitter_account, attribute_names=["user"])
            await session.refresh(self.account, attribute_names=["user"])
            await session.refresh(self.account.user, attribute_names=["twitter_user"])

        if not self.account.twitter_account:
            logger.warning(f"{self.account} No Twitter account")
            return False

        # TODO Вынести эту конструкцию как @property MintAccount.better_proxy
        proxy = None
        if self.account.proxy:
            proxy = self.account.proxy.better_proxy

        # Проверяем, запрошена ли информация о пользователе Twitter
        if not self.account.twitter_account.user:
            async with TwitterClient(self.account.twitter_account, proxy=proxy):
                # Здесь неявно запрашивается информация о пользователе
                pass

        # TODO Использовать атрибут twitter_account.bound
        if self.account.user.twitter_id and self.account.twitter_account.user:
            # Если это тот же пользователь, то все ок
            if self.account.user.twitter_id == self.account.twitter_account.user.id:
                logger.info(f"{self.account} {self.account.twitter_account.user}"
                            f" Twitter account already bound")
                return False

            # Если это другой пользователь, значит у нас каким-то образом дубликат,
            # хотя такого не может быть, так как бд не позволит.
            # Поэтому проверку делать бессмысленно
            else:
                pass

        # Если же пользователь не привязан, то проверяем дату создания (если информация есть в бд)
        # if mint_account.twitter_account.user:
        #     twitter_user: TwitterUser = mint_account.twitter_account.user
        #     one_month_ago = datetime.now() - timedelta(days=30)  # Примерное определение месяца как 30 дней
        #     if twitter_user.created_at <= one_month_ago:
        #         logger.warning(f"{mint_account} {twitter_user}"
        #                        f" Слишком молодой твиттер аккаунт."
        #                        f" Возраст твиттер аккаунта должен быть более 30 дней")
        #         return

        # Проверку на срок было решено отключить, так как, если что, api mintchain просто вернет ошибку в запросе

        async with TwitterClient(self.account.twitter_account, proxy=proxy) as twitter_client:  # type: TwitterClient

            # if twitter_client.account.followers_count < 10:
            #     raise TwitterScriptError(
            #         self.account.twitter_account,
            #         f"Necessary condition: Twitter followers >= 10."
            #         f" Yours: {twitter_client.account.followers_count}"
            #     )

            # Проверку на срок было решено не делать, так как, если что, api mintchain просто вернет ошибку в запросе

            auth_code = await twitter_client.oauth2(**TWITTER_OAUTH2_PARAMS)

        try:
            self.account.user.twitter_id = await self.http.bind_twitter(self.account.wallet.address, auth_code)
            logger.success(f"{self.account} Twitter bound")
        except HTTPException as exc:
            if exc.message == "Necessary condition: followers >= 10":
                raise TwitterScriptError(
                    self.account.twitter_account,
                    f"Necessary condition: Twitter followers >= 10."
                    f" Yours: {twitter_client.account.followers_count}"
                )
            else:
                raise
            # TODO Делать проверка на ошибку bound_to_another_mint_user

        # Сохраняем информацию об аккаунте в БД
        async with AsyncSessionmaker() as session:
            session.add(self.account)
            await session.commit()

        return True
