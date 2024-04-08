from pydantic import BaseModel

from .logger import LoggingLevel


class LoggingConfig(BaseModel):
    LEVEL: LoggingLevel = "INFO"


class ConcurrencyConfig(BaseModel):
    MAX_TASKS: int = 1
    MAX_RETRIES: int = 3
    DELAY_BETWEEN_RETRIES: int = 5
    DELAY_BETWEEN_ACTIONS: tuple[int, int] = (0, 0)
    DELAY_BETWEEN_ACCOUNTS: tuple[int, int] = (0, 0)


class RequestsConfig(BaseModel):
    TIMEOUT: int = 30


class TwitterConfig(BaseModel):
    AUTO_RELOGIN: bool = True
    MAX_UNLOCK_ATTEMPTS: int = 5
    USE_SUSPENDED_ACCOUNTS: bool = False


class CaptchaConfig(BaseModel):
    CAPSOLVER_API_KEY: str | None = None


class TransactionConfig(BaseModel):
    TIMEOUT: float = 0.0  # Сколько секунд ждать выполнения транзакции (0 - не ждать)


class PlaywrightConfig(BaseModel):
    HEADLESS: bool = True
    TIMEOUT: int = 30
    TIME_TO_WAIT: int = 10


class MobileProxyConfig(BaseModel):
    PROXY: str | None = None
    CHANGE_IP_URL: str | None = None


class ImportConfig(BaseModel):
    TWITTER_SEPARATOR: str = ":"
    DISCORD_SEPARATOR: str = ":"
    GOOGLE_SEPARATOR: str = ":"
    TWITTER_FIELDS: tuple[str] = ("auth_token", "username", "password", "totp_secret")
    DISCORD_FIELDS: tuple[str] = ("auth_token", "email", "password")
    GOOGLE_FIELDS: tuple[str] = ("email", "password", "recovery_email", "totp_secret")
