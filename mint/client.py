from functools import wraps
from random import randint

from loguru import logger

from .database import AsyncSessionmaker, MintAccount, MintUser, update_or_create
from .api.http import HTTPClient
from .api.errors import HTTPException
from .api.models import Task
from .twitter import TwitterClient
from .errors import TooLessTwitterFollowers


TWITTER_OAUTH2_PARAMS = {
    'state': 'mintchain',
    'code_challenge_method': 'plain',
    'code_challenge': 'mintchain',
    'client_id': 'enpfUjhndkdrdHhld29aTW96eGM6MTpjaQ',
    'scope': 'tweet.read users.read follows.read offline.access',
    'response_type': 'code',
    'redirect_uri': 'https://www.mintchain.io/mint-forest',
}


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
        self.http._session.proxy = account.proxy.better_proxy

    async def relogin(self):
        nonce = randint(1_000_000, 9_999_999)
        better_wallet = self.account.wallet.better_wallet
        message = (f"You are participating in the Mint Forest event: "
                   f"\n {better_wallet.address}"
                   f"\n\nNonce: {nonce}")
        signature = better_wallet.sign_message(message)
        user = await self.http.login(better_wallet.address, message, signature)
        async with AsyncSessionmaker() as session:
            session.add(self.account)
            self.account.auth_token = self.http.auth_token
            self.account.user, _ = await update_or_create(session, MintUser, user.model_dump(exclude={"signs"}), id=user.id)
            await session.commit()
        logger.success(f"{self.account} Logged in")

    async def login(self):
        if self.account.auth_token:
            logger.info(f"{self.account} Using saved auth_token")
            return

        await self.relogin()

    @staticmethod
    def relogin_on_error(method):
        @wraps(method)
        async def wrapper(self, *args, **kwargs):
            # return await method(self, *args, **kwargs)
            try:
                return await method(self, *args, **kwargs)
            except HTTPException as exc:
                if exc.message == "Authentication failed":
                    raise

                await self.relogin()
                return await method(self, *args, **kwargs)

        return wrapper

    @relogin_on_error
    async def bind_discord(self, auth_code):
        # TODO Discord binding
        ...

    @relogin_on_error
    async def try_to_accept_invite(self):
        if self.account.user.inviter_user_id:
            logger.info(f"{self.account}  Account already invited."
                        f"\n\tInviter user ID: {self.account.user.inviter_user_id}")
            return

        async with AsyncSessionmaker() as session:
            session.add(self.account)
            self.account.user.inviter_user_id = await self.http.accept_invite(self.account.invite_code)
            await session.commit()
        logger.success(f"{self.account} Account invited!"
                       f"\n\tInviter user ID: {self.account.user.inviter_user_id}"
                       f"\n\tInvite code: {self.account.invite_code}")

    @relogin_on_error
    async def claim_energy(self):
        energy_list = await self.http.request_energy_list()
        for energy in energy_list:
            if not energy.freeze:
                claimed_me = await self.http.claim_energy(id=f"{energy.amount}_", **energy.model_dump())
                logger.success(f"{self.account} Claimed {claimed_me} energy")

        assets = await self.http.request_assets()
        for asset in assets:
            if not asset.type == "energy":
                continue

            claimed_me = await self.http.open_box(asset.id)
            logger.success(f"{self.account} Box claimed! Claimed {claimed_me} energy")

    @relogin_on_error
    async def complete_tasks(self):
        tasks = await self.http.request_task_list()
        unclaimed_tasks: list[Task] = [task for task in tasks if not task.claimed]
        for task in unclaimed_tasks:
            if task.spec.startswith("twitter"):
                claimed_me = await self.http.sumbit_task(task.id)
                logger.success(f"{self.account} Task '{task.name}' completed! Claimed {claimed_me} energy")

        # TODO Bridge task
        # TODO Discord task

    @relogin_on_error
    async def request_self(self):
        user = await self.http.request_self()
        async with AsyncSessionmaker() as session:
            session.add(self.account)
            # По сути это как update из Django ORM
            for key, value in user.model_dump().items():
                setattr(self.account.user, key, value)
            await session.commit()
        logger.info(f"{self.account} User data requested")

    @relogin_on_error
    async def inject_all(self):
        await self.request_self()
        if not self.account.user.me:
            return

        await self.http.inject(self.account.user.me, self.account.wallet.address)

    @relogin_on_error
    async def try_to_verify_wallet(self):
        if self.account.user.status == "verified":
            return

        try:
            await self.http.verify_wallet()
        except HTTPException as exc:
            if not exc.message == "Wallet was registed, please login again":
                raise

            logger.info(f"{self.account} Wallet already verified.")
            await self.relogin()
            await self.request_self()

        logger.success(f"{self.account} Wallet verified!")

    @relogin_on_error
    async def try_to_bind_twitter(self):
        # Подразумевается, что MintAccount.twitter_account уже запрошен из бд
        # Если пользователь не передал Twitter аккаунт, значит игнорируем
        if not self.account.twitter_account:
            logger.warning(f"{self.account}"
                           f" No Twitter account")
            return

        # Подразумевается, что MintAccount.user уже запрошен из бд
        mint_user: MintUser = self.account.user

        # Запрашиваем MintUser.twitter_user
        async with AsyncSessionmaker() as session:
            session.add(self.account)
            await session.refresh(mint_user, attribute_names=["twitter_user"])
            await session.refresh(self.account.twitter_account, attribute_names=["user"])

        # Если у MintUser уже есть привязанный пользователь Twitter
        # TODO возможно, потребуется проверка на mint_account.twitter_account.user.
        #   Если его нету, то нужно запросить через апи

        # TODO Использовать параметр twitter_account.bound
        if mint_user.twitter_user and self.account.twitter_account.user:

            # Если это тот же пользователь, то все ок
            if mint_user.twitter_user == self.account.twitter_account.user:
                logger.info(f"{self.account} {self.account.twitter_account.user}"
                            f" Twitter account already bound")
                return

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

        async with TwitterClient(self.account.twitter_account, proxy=self.account.proxy.better_proxy) as twitter_client:  # type: TwitterClient
            await twitter_client.request_user()

            # TODO Эту проверку нужно сделать опциональной
            if twitter_client.account.followers_count < 10:
                raise TooLessTwitterFollowers(
                    self.account,
                    f"Necessary condition: Twitter followers >= 10."
                    f" Yours: {twitter_client.account.followers_count}"
                )

            # Проверку на срок было решено не делать, так как, если что, api mintchain просто вернет ошибку в запросе

            auth_code = await twitter_client.oauth_2(**TWITTER_OAUTH2_PARAMS)

            async with AsyncSessionmaker() as session:
                session.add(self.account)
                try:
                    self.account.user.twitter_id = await self.http.bind_twitter(self.account.wallet.address, auth_code)
                except HTTPException as exc:
                    if exc.message == "Necessary condition: followers >= 10":
                        raise TooLessTwitterFollowers(
                            self.account,
                            f"Necessary condition: Twitter followers >= 10."
                            f" Yours: {twitter_client.account.followers_count}"
                        )
                    else:
                        raise
                    # TODO Делать проверка на ошибку bound_to_another_mint_user
                await session.commit()
            logger.success(f"{self.account} Twitter bound")
