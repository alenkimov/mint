from pydantic import BaseModel

from better_web3 import Wallet
import twitter

from .api.models import User


class Account(BaseModel):
    model_config = {
        "arbitrary_types_allowed": True
    }

    token: str | None = None
    user: User | None = None
    wallet: Wallet
    twitter: twitter.Account
    referrer_invite_code: str

    def __str__(self):
        return str(self.twitter)
