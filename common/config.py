from pydantic import BaseModel

from .logger import LoggingLevel


class LoggingConfig(BaseModel):
    LEVEL: LoggingLevel = "INFO"


class MobileProxyConfig(BaseModel):
    PROXY: str | None = None
    CHANGE_IP_URL: str | None = None


class ConcurrencyConfig(BaseModel):
    MAX_TASKS: int = 1
    MAX_RETRIES: int = 3
    DELAY: tuple[int, int] = (0, 0)


class PlaywrightConfig(BaseModel):
    HEADLESS: bool = True
    TIMEOUT: int = 30_000
    TIME_TO_WAIT: int = 10_000


class ImportConfig(BaseModel):
    TWITTER_SEPARATOR: str = ":"
    DISCORD_SEPARATOR: str = ":"
    GOOGLE_SEPARATOR: str = ":"
    TWITTER_FIELDS: tuple[str] = ("auth_token", "email", "password", "totp_secret")
    DISCORD_FIELDS: tuple[str] = ("auth_token", "email", "password", "username")
    GOOGLE_FIELDS: tuple[str] = ("email", "password", "totp_secret")


class TwitterConfig(BaseModel):
    UNLOCK_ATTEMPTS: int = 5
    USE_SUSPENDED_ACCOUNTS: bool = False


class CaptchaConfig(BaseModel):
    CAPSOLVER_API_KEY: str | None = None


class TransactionConfig(BaseModel):
    WAIT_FOR_TX_RECEIPT: bool = False
