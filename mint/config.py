from pydantic import BaseModel

from common.utils import load_toml

from common.config import (
    LoggingConfig,
    TwitterConfig,
    CaptchaConfig,
    ConcurrencyConfig,
    RequestsConfig,
    TransactionConfig,
)
from .paths import CONFIG_TOML


class BridgeConfig(BaseModel):
    SEPOLIA_ETH_BRIDGE_AMOUNT_RANGE: tuple[float, float] = (0.001, 0.0011)
    MINTCHAIN_ETH_BRIDGE_AMOUNT_RANGE: tuple[float, float] = (0.0001, 0.0005)


class TasksConfig(BaseModel):
    TASK_IDS_TO_IGNORE: tuple = (6, )


class Config(BaseModel):
    LOGGING: LoggingConfig
    CONCURRENCY: ConcurrencyConfig
    TWITTER: TwitterConfig
    CAPTCHA: CaptchaConfig
    REQUESTS: RequestsConfig
    TRANSACTION: TransactionConfig
    BRIDGE: BridgeConfig
    TASKS: TasksConfig


CONFIG = Config(**load_toml(CONFIG_TOML))

VALID_TWITTER_STATUSES = ["UNKNOWN", "GOOD"]
if CONFIG.TWITTER.USE_SUSPENDED_ACCOUNTS:
    VALID_TWITTER_STATUSES.append("SUSPENDED")
if CONFIG.CAPTCHA.CAPSOLVER_API_KEY:
    VALID_TWITTER_STATUSES.append("LOCKED")

