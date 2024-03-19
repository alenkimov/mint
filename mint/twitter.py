from loguru import logger

import twitter

from .config import CONFIG

from .database import MintAccount, TwitterUser


class TwitterClient:
    def __init__(self, mint_account: MintAccount):
        self.mint_account = mint_account
        self.http: twitter.Client | None = None
        self.twitter_account: twitter.Account | None = None

    async def __aenter__(self):
        self.twitter_account = twitter.Account(
            auth_token=self.mint_account.twitter_account.auth_token,
            ct0=self.mint_account.twitter_account.ct0,
            username=self.mint_account.twitter_account.username,
            password=self.mint_account.twitter_account.password,
            email=self.mint_account.twitter_account.email,
            totp_secret=self.mint_account.twitter_account.totp_secret,
            backup_code=self.mint_account.twitter_account.backup_code,
            status=self.mint_account.twitter_account.status,
        )
        if self.mint_account.twitter_account.user:
            self.twitter_account.id = self.mint_account.twitter_account.user.id
            # Поле username есть в обоих моделях
            self.twitter_account.username = (self.mint_account.twitter_account.user.username
                                             or self.mint_account.twitter_account.username)
            self.twitter_account.name = self.mint_account.twitter_account.user.name
            self.twitter_account.created_at = self.mint_account.twitter_account.user.created_at
            self.twitter_account.description = self.mint_account.twitter_account.user.description
            self.twitter_account.location = self.mint_account.twitter_account.user.location
            self.twitter_account.followers_count = self.mint_account.twitter_account.user.followers_count
            self.twitter_account.friends_count = self.mint_account.twitter_account.user.friends_count

        proxy = None
        if self.mint_account.proxy:
            proxy = self.mint_account.proxy.better_proxy

        self.http = twitter.Client(
            self.twitter_account,
            max_unlock_attempts=CONFIG.TWITTER.UNLOCK_ATTEMPTS,
            capsolver_api_key=CONFIG.CAPTCHA.CAPSOLVER_API_KEY,
            proxy=proxy,
        )
        return self

    async def __aexit__(self, *args):
        await self.close()

    async def close(self):
        twitter_account_data = self.twitter_account.model_dump(
            include={"auth_token", "ct0", "username", "password", "email", "totp_secret", "backup_code", "status"}
        )
        await self.mint_account.twitter_account.update_from_dict(twitter_account_data)

        twitter_user_data = self.twitter_account.model_dump(
                include={"id", "username", "name", "created_at", "description", "location", "followers_count", "friends_count"}
            )
        self.mint_account.twitter_account.user, _ = await TwitterUser.update_or_create(**twitter_user_data)
        await self.mint_account.twitter_account.save()
        self.http.close()

    async def oauth2(self, **oauth2_params) -> str:
        auth_code = await self.http.oauth_2(**oauth2_params)
        logger.info(f"{self.mint_account} {self.twitter_account} Requested oauth2 code")
        return auth_code
