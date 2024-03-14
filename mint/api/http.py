from typing import Any

from loguru import logger
from curl_cffi import requests
from twitter.base import BaseClient
from twitter.utils import hidden_value
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_fixed

from .models import User, Task, Energy
from .errors import HTTPException


class HTTPClient(BaseClient):
    _DEFAULT_HEADERS = {
        'authorization': 'Bearer',
    }

    def __init__(self, token: str = None, **session_kwargs):
        super().__init__(**session_kwargs)
        self.token = token

    @property
    def hidden_token(self) -> str | None:
        if not self.token:
            return None

        return hidden_value(self.token)

    async def request(
        self,
        method,
        url,
        *,
        auth: bool = True,
        query_auth: bool = False,
        **kwargs,
    ) -> tuple[requests.Response, Any]:
        # cookies = kwargs["cookies"] = kwargs.get("cookies") or {}
        headers = kwargs["headers"] = kwargs.get("headers") or {}
        params = kwargs["params"] = kwargs.get("params") or {}

        if self.token and auth:
            if query_auth:
                params["jwtToken"] = self.token
            else:
                headers["authorization"] = f"Bearer {self.token}"

        # fmt: off
        log_message = f"[{self.hidden_token}] Request {method} {url}"
        if kwargs.get('data'): log_message += f"\nRequest data: {kwargs.get('data')}"
        if kwargs.get('json'): log_message += f"\nRequest data: {kwargs.get('json')}"
        logger.debug(log_message)
        # fmt: on

        response = await self._session.request(method, url, **kwargs)

        data = response.text
        if response.headers["content-type"].startswith("application/json"):
            data = response.json()

        # fmt: off
        log_message = (f"[{self.hidden_token}] Response {method} {url}"
                       f"\nStatus code: {response.status_code}"
                       f"\nResponse data: {data}")
        logger.debug(log_message)
        # fmt: on

        if 300 > response.status_code >= 200:
            if isinstance(data, dict):
                if data["code"] != 10000:
                    raise HTTPException(response, data)

                data = data["result"]

            return response, data

        raise HTTPException(response, data)

    async def login(self, address: str, message: str, signature: str) -> User:
        url = "https://www.mintchain.io/api/tree/login"
        payload = {
            "address": address,
            "signature": signature,
            "message": message,
        }

        response, data = await self.request("POST", url, json=payload)
        self.token = data["access_token"]
        user = User(**data["user"])
        return user

    def is_http_exception_with_code_10001(exception):
        """Проверка, является ли исключение HTTPException с кодом 10001."""
        return isinstance(exception, HTTPException) and exception.code == 10001

    @retry(
        retry=retry_if_exception(lambda exc: isinstance(exc, HTTPException) and exc.code == 10001),
        stop=stop_after_attempt(3),
        wait=wait_fixed(30),
    )
    async def bind_twitter(self, address: str, auth_code: str):
        url = "https://www.mintchain.io/api/twitter/verify"
        payload = {}
        query = {
            'address': address,
            'code': auth_code,
        }
        response, data = await self.request("POST", url, data=payload, params=query, query_auth=True)
        twitter_user_id = data
        return twitter_user_id

    async def accept_invite(self, invite_code: str):
        """
        :return: Invited ID
        """
        url = "https://www.mintchain.io/api/tree/invitation"
        query = {"code": invite_code}
        payload = {}
        response, data = await self.request("GET", url, data=payload, params=query, query_auth=True)
        invited_id = data["inviteId"]
        return invited_id

    async def request_user(self):
        url = "https://www.mintchain.io/api/tree/user-info"
        payload = {}
        response, data = await self.request("GET", url, data=payload)
        return User(**data)

    async def request_energy_list(self) -> list[Energy]:
        """
        :return: Energy list
        """
        url = "https://www.mintchain.io/api/tree/energy-list"
        payload = {}
        response, data = await self.request("GET", url, data=payload)
        energy_list = [Energy(**energy_data) for energy_data in data]
        return energy_list

    async def claim_energy(
            self,
            *,
            id: str,
            uid: list,
            type: str,
            amount: int,
            includes: list,
            freeze: bool = False,
    ) -> int:
        """
        :return: ME amount
        """
        url = "https://www.mintchain.io/api/tree/claim"
        payload = {
            "uid": uid,
            "amount": amount,
            "includes": includes,
            "type": type,
            "freeze": freeze,
            "id": id,
        }
        response, data = await self.request("POST", url, json=payload)
        me_amount = data
        return me_amount

    async def request_task_list(self) -> list[Task]:
        url = "https://www.mintchain.io/api/tree/task-list"
        payload = {}
        response, data = await self.request("GET", url, data=payload)
        tasks = [Task(**task_data) for task_data in data]
        return tasks

    async def sumbit_task(self, task_id: int):
        """
        :return: ME amount
        """
        url = "https://www.mintchain.io/api/tree/task-submit"
        payload = {"id": task_id}
        response, data = await self.request("POST", url, json=payload)
        me_amount = data["amount"]
        return me_amount
