from better_proxy import Proxy as BetterProxy
import twitter

from .config import CONFIG

from .database import (
    AsyncSessionmaker,
    update_or_create,
    TwitterAccount,
    TwitterUser,
)


class TwitterClient(twitter.Client):
    """
    - Принимает модель TwitterAccount
    - Сохраняет данные о TwitterAccount и TwitterAccount.user в бд по завершении работы
    """

    def __init__(self, twitter_account: TwitterAccount, proxy: str | BetterProxy):
        self.db_account = twitter_account

        # Сюда можно передавать данные о пользователе (TwitterAccount.user),
        # но это необязательно, поэтому не будем запариваться
        account = twitter.Account(
            auth_token=self.db_account.auth_token,
            ct0=self.db_account.ct0,
            username=self.db_account.username,
            password=self.db_account.password,
            email=self.db_account.email,
            totp_secret=self.db_account.totp_secret,
            backup_code=self.db_account.backup_code,
            status=self.db_account.status,
        )
        super().__init__(
            account,
            proxy=proxy,
            max_unlock_attempts=CONFIG.TWITTER.UNLOCK_ATTEMPTS,
            capsolver_api_key=CONFIG.CAPTCHA.CAPSOLVER_API_KEY,
        )

    async def __aexit__(self, *args):
        await self.close()

    async def close(self):
        async with AsyncSessionmaker() as session:
            twitter_account_data = self.account.model_dump(
                include={"id", "auth_token", "ct0", "username", "password", "email", "totp_secret", "backup_code", "status"}
            )
            session.add(self.db_account)
            # По сути это как update из Django ORM
            for key, value in twitter_account_data.items():
                setattr(self.db_account, key, value)

            twitter_user_data = self.account.model_dump(
                    include={"id", "username", "name", "created_at", "description", "location", "followers_count", "friends_count"}
                )

            self.db_account.user, _ = await update_or_create(
                session, TwitterUser, twitter_user_data, id=twitter_user_data["id"])
            await session.commit()

        await super().close()
