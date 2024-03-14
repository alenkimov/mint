import asyncio

from loguru import logger

from .logger import LoggingLevel


async def sleep(seconds: float, logging_level: LoggingLevel = "INFO", account=None):
    if seconds <= 0:
        return

    log_message = f"{account} " if account is not None else ""
    log_message += f"Sleeping {seconds:.1f} sec."
    logger.log(logging_level, log_message)
    await asyncio.sleep(seconds)
