"""
Twitter scripts (binding)
"""

import twitter

from ..client import Client
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


async def try_to_bind_twitter(mint_client: Client, proxy):
    if mint_client.account.user.twitter:
        return

        # TODO Проверка на срок через бд

    async with twitter.Client(mint_client.account.twitter, proxy=proxy) as twitter_client:
        twitter_user_data = await twitter_client.request_user_data()

        if twitter_user_data.followers_count < 10:
            raise TooLessTwitterFollowers(
                mint_client.account,
                f"Necessary condition: Twitter followers >= 10. Yours: {twitter_user_data.followers_count}"
            )

        # TODO Проверка на срок, если в бд нет инфы

        auth_code = await twitter_client.oauth_2(**TWITTER_OAUTH2_PARAMS)
        await mint_client.bind_twitter(auth_code)
