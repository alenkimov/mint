from random import randint

from loguru import logger

from .database import MintAccount, MintUser
from .api.http import HTTPClient
from .api.models import Task


class Client:
    def __init__(self, account: MintAccount, **session_kwargs):
        self._account = None
        self.http = HTTPClient(**session_kwargs)
        self.account = account

    @property
    def account(self) -> MintAccount:
        return self._account

    @account.setter
    def account(self, account: MintAccount):
        self._account = account
        self.http.auth_token = account.auth_token
        self.http._session.proxy = account.proxy.better_proxy

    async def login(self):
        if self.account.auth_token:
            logger.info(f"{self.account} Using saved auth_token")
            return

        nonce = randint(1_000_000, 9_999_999)
        better_wallet = self.account.wallet.better_wallet
        message = (f"You are participating in the Mint Forest event: "
                   f"\n {better_wallet.address}"
                   f"\n\nNonce: {nonce}")
        signature = better_wallet.sign_message(message)
        user = await self.http.login(better_wallet.address, message, signature)
        self.account.auth_token = self.http.auth_token
        self.account.user, _ = await MintUser.update_or_create(**user.model_dump(exclude={"signs"}))
        await self.account.user.save()
        await self.account.save()
        logger.success(f"{self.account} Logged in")

    async def bind_twitter(self, auth_code):
        self.account.user.twitter_id = await self.http.bind_twitter(self.account.wallet.address, auth_code)
        self.account.twitter_account.bound = True
        await self.account.user.save()
        await self.account.twitter_account.save()
        logger.success(f"{self.account} Twitter bound")

    async def bind_discord(self, auth_code):
        # TODO Discord binding
        ...

    async def accept_invite(self):
        self.account.user.invite_id = await self.http.accept_invite(self.account.invite_code)
        await self.account.user.save()
        logger.success(f"{self.account} Account invited by {self.account.invite_code}")

    async def claim_energy(self):
        energy_list = await self.http.request_energy_list()
        for energy in energy_list:
            if not energy.freeze:
                claimed_me = await self.http.claim_energy(id=f"{energy.amount}_", **energy.model_dump())
                logger.success(f"{self.account} Claimed {claimed_me} energy")

    async def complete_tasks(self):
        tasks = await self.http.request_task_list()
        unclaimed_tasks: list[Task] = [task for task in tasks if not task.claimed]
        for task in unclaimed_tasks:
            if task.spec.startswith("twitter"):
                claimed_me = await self.http.sumbit_task(task.id)
                logger.success(f"{self.account} Task '{task.name}' completed! Claimed {claimed_me} energy")

        # TODO Bridge task
        # TODO Discord task

    async def request_self(self):
        user = await self.http.request_self()
        self.account.user.update_from_dict(user.model_dump())
        await self.account.user.save()
        logger.info(f"{self.account} User data requested")

    async def inject_all(self):
        await self.request_self()
        if not self.account.user.me:
            return

        await self.http.inject(self.account.user.me, self.account.wallet.address)
