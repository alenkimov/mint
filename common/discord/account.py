from pydantic import BaseModel
import twitter

from .enums import AccountStatus, RequiredAction


class Account(BaseModel):
    auth_token: str | None = None
    username:   str | None = None
    email:      str | None = None
    phone:      str | None = None
    name:       str | None = None
    id:         int | None = None

    status: AccountStatus = AccountStatus.UNKNOWN
    required_action: RequiredAction | None = None

    @property
    def hidden_auth_token(self) -> str | None:
        return twitter.utils.hidden_value(self.auth_token) if self.auth_token else None

    @property
    def hidden_password(self) -> str | None:
        return twitter.utils.hidden_value(self.password) if self.password else None

    def __str__(self):
        representation = f"[{self.hidden_auth_token}]"
        if self.username:
            representation += f"(@{self.username})"
        return representation
