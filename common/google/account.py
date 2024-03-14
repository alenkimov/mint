from pydantic import BaseModel
import pyotp

from twitter.utils import hidden_value

from .enums import AccountStatus


MAX_EMAIL_LENGTH: int = 32


class Account(BaseModel):

    email:          str
    password:       str
    recovery_email: str | None = None
    totp_secret:    str | None = None
    cookies:        list | None = None
    status: AccountStatus = "UNKNOWN"

    @property
    def hidden_password(self) -> str | None:
        return hidden_value(self.password) if self.password else None

    @property
    def hidden_totp_secret(self) -> str | None:
        return hidden_value(self.totp_secret) if self.totp_secret else None

    @property
    def email_fixed_length(self) -> str:
        return f"[{self.email:<{MAX_EMAIL_LENGTH}}]"

    def __repr__(self):
        return f"{self.__class__.__name__}(email={self.email})"

    def __str__(self):
        return self.email

    def get_totp_code(self) -> str | None:
        if not self.totp_secret:
            raise ValueError("No totp_secret!")

        return str(pyotp.TOTP(self.totp_secret).now())
