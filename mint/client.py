from random import randint

from loguru import logger

from .account import Account
from .api.http import HTTPClient
from .api.models import Task


class Client:
    def __init__(self, account: Account, **session_kwargs):
        self._account = None
        self.http = HTTPClient(**session_kwargs)
        self.account = account

    @property
    def account(self) -> Account:
        return self._account

    @account.setter
    def account(self, account: Account):
        self._account = account
        self.http.token = account.token

    async def login(self):
        nonce = randint(1_000_000, 9_999_999)
        message = (f"You are participating in the Mint Forest event: "
                   f"\n {self.account.wallet.address}"
                   f"\n\nNonce: {nonce}")
        signature = self.account.wallet.sign_message(message)
        self.account.user = await self.http.login(self.account.wallet.address, message, signature)
        self.account.token = self.http.token

    async def bind_twitter(self, auth_code):
        self.account.user.twitter = await self.http.bind_twitter(self.account.wallet.address, auth_code)

    async def accept_invite(self):
        self.account.user.invite_id = await self.http.accept_invite(self.account.referrer_invite_code)

    async def claim_energy(self):
        energy_list = await self.http.request_energy_list()
        for energy in energy_list:
            if not energy.freeze:
                claimed_me = await self.http.claim_energy(**energy.model_dump())
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

    # TODO Полив дерева
    # TODO Привязка дискорда
