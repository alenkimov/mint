from typing import Any

from loguru import logger
from curl_cffi import requests
from twitter.base import BaseHTTPClient
from twitter.utils import hidden_value
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_fixed

from .models import User, Task, Energy, Asset
from .errors import HTTPException


class HTTPClient(BaseHTTPClient):
    _DEFAULT_HEADERS = {
        'authority': 'www.mintchain.io',
        'authorization': 'Bearer',
    }

    def __init__(self, auth_token: str = None, **session_kwargs):
        super().__init__(**session_kwargs)
        self.auth_token = auth_token

    @property
    def hidden_token(self) -> str | None:
        if not self.auth_token:
            return None

        return hidden_value(self.auth_token)

    async def request(
        self,
        method,
        url,
        *,
        auth: bool = True,
        query_auth: bool = False,
        payload_auth: bool = False,
        **kwargs,
    ) -> tuple[requests.Response, Any]:
        # cookies = kwargs["cookies"] = kwargs.get("cookies") or {}

        if self.auth_token and auth:
            if query_auth:
                params = kwargs["params"] = kwargs.get("params") or {}
                params["jwtToken"] = self.auth_token
            if payload_auth:
                payload = kwargs["json"] = kwargs.get("json") or {}
                payload["jwtToken"] = self.auth_token
            else:
                headers = kwargs["headers"] = kwargs.get("headers") or {}
                headers["authorization"] = f"Bearer {self.auth_token}"

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
        self.auth_token = data["access_token"]
        return User(**data["user"])

    # @retry(
    #     retry=retry_if_exception(lambda exc: isinstance(exc, HTTPException) and exc.message == ""),
    #     stop=stop_after_attempt(3),
    #     wait=wait_fixed(30),
    # )
    async def bind_twitter(self, address: str, auth_code: str) -> int:
        url = "https://www.mintchain.io/api/twitter/verify"
        query = {
            'address': address,
            'code': auth_code,
        }
        response, data = await self.request("POST", url, params=query, query_auth=True)
        twitter_id = int(data)
        return twitter_id

    async def accept_invite(self, invite_code: str) -> int:
        """
        :return: Invited ID
        """
        url = "https://www.mintchain.io/api/tree/invitation"
        query = {"code": invite_code}
        response, data = await self.request("GET", url, params=query, query_auth=True)
        return data["inviteId"]

    async def request_self(self) -> User:
        url = "https://www.mintchain.io/api/tree/user-info"
        response, data = await self.request("GET", url)
        return User(**data)

    async def request_energy_list(self) -> list[Energy]:
        """
        :return: Energy list
        """
        url = "https://www.mintchain.io/api/tree/energy-list"
        payload = {}
        response, data = await self.request("GET", url, data=payload)
        return [Energy(**energy_data) for energy_data in data]

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
        return data

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

    async def inject(self, me_amount: int, address: str) -> bool:
        url = "https://www.mintchain.io/api/tree/inject"
        payload = {
            "energy": me_amount,
            "address": address
        }
        response, data = await self.request("POST", url, json=payload)
        return data

    async def request_assets(self) -> list[Asset]:
        url = "https://www.mintchain.io/api/tree/asset"
        payload = {}
        response, data = await self.request("GET", url, data=payload)
        return [Asset(**asset_data) for asset_data in data]

    async def open_box(self, box_id: int) -> int | None:
        url = "https://www.mintchain.io/api/tree/open-box"
        payload = {"boxId": box_id}
        response, data = await self.request("POST", url, data=payload)
        return data["energy"]

    async def verify_wallet(self) -> bool:
        """
        :return: Verified or not
        """
        url = "https://www.mintchain.io/api/wallet/verify"
        response, data = await self.request("POST", url, payload_auth=True)
        return data["data"]
