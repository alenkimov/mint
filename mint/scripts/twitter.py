"""
Twitter scripts (binding)
"""
from datetime import datetime, timedelta

from loguru import logger

from ..client import Client as MintClient
from ..twitter import TwitterClient
from .errors import TooLessTwitterFollowers

from ..database import MintUser, MintAccount


TWITTER_OAUTH2_PARAMS = {
    'state': 'mintchain',
    'code_challenge_method': 'plain',
    'code_challenge': 'mintchain',
    'client_id': 'enpfUjhndkdrdHhld29aTW96eGM6MTpjaQ',
    'scope': 'tweet.read users.read follows.read offline.access',
    'response_type': 'code',
    'redirect_uri': 'https://www.mintchain.io/mint-forest',
}


async def try_to_bind_twitter(mint_client: MintClient):
    mint_account: MintAccount = mint_client.account

    # Если пользователь не передал Twitter аккаунт, значит игнорируем
    if not mint_account.twitter_account:
        logger.warning(f"{mint_client.account}"
                       f" No Twitter account")
        return

    # К этому моменту пользователь должен уже быть запрошен
    mint_user: MintUser = mint_account.user

    # Если у mint пользователя уже есть привязанный пользователь Twitter
    if mint_user.twitter_user:
        # TODO возможно, потребуется проверка на mint_account.twitter_account.user

        # Если этот тот же пользователь, то все ок
        if mint_user.twitter_user.id == mint_account.twitter_account.user.id:
            logger.info(f"{mint_account} {mint_client.account.twitter_account.user}"
                        f" Twitter account already bound")

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
    #                        f" Слишком молодой твиттер аккаунт. Возраст твиттер аккаунта должен быть более 30 дней")
    #         return

    # Проверку на срок было решено отключить, так как, если что, api mintchain просто вернет ошибку в запросе

    async with TwitterClient(mint_account) as twitter_client:
        await twitter_client.http.request_user()

        if twitter_client.twitter_account.followers_count < 10:
            raise TooLessTwitterFollowers(
                mint_client.account,
                f"Necessary condition: Twitter followers >= 10."
                f" Yours: {twitter_client.twitter_account.followers_count}"
            )

        # Проверку на срок было решено не делать, так как, если что, api mintchain просто вернет ошибку в запросе

        auth_code = await twitter_client.oauth2(**TWITTER_OAUTH2_PARAMS)
        await mint_client.bind_twitter(auth_code)
