"""
Ошибки, на которых нужно останавливать весь скрипт:
- Любые неожиданные ошибки

Ошибки, на которых нужно останавливать действие:
- Предусмотренные ошибки логики скрипта

Ошибки на которых нужно делать повтор действия:
- Ошибка запроса, связанная с прокси
- Ошибка запроса, связанные с сервером
"""

import asyncio
from typing import Callable
from random import randint

from eth_account import Account as Wallet
from eth_account.account import LocalAccount
from better_proxy import Proxy as BetterProxy
from twitter.errors import HTTPException as TwitterHTTPException, BadAccount as TwitterBadAccountError

import questionary
from loguru import logger
from curl_cffi import requests

from common.project import print_project_info
from common.author import print_author_info
from common.logger import setup_logger
from common.excell import get_xlsx_filepaths, get_worksheets

from mint.paths import INPUT_DIR, DATABASE_FILEPATH, LOG_DIR
from mint.config import CONFIG
from mint.excell import excell
from mint.client import Client as MintClient
from mint.api.errors import HTTPException as MintHTTPException
from mint.errors import DiscordScriptError, TwitterScriptError
from mint.database.crud import (
    get_accounts_by_groups,
    get_groups,
    get_or_create,
    update_or_create,
)
from mint.database import (
    AsyncSessionmaker,
    alembic_utils,
    MintAccount,
    DiscordAccount,
    TwitterAccount,
    Proxy,
    Wallet,
)

setup_logger(LOG_DIR, CONFIG.LOGGING.LEVEL)
logger.enable("twitter")

DATABASE_URL = f"sqlite:///{DATABASE_FILEPATH}"


async def exit():
    quit()


async def select_and_import_table():
    table_filepaths = get_xlsx_filepaths(INPUT_DIR)

    if len(table_filepaths) == 0:
        template_table_filepath = excell.create_empty_table(INPUT_DIR, "template")
        print(f"Created template XLSX table: {template_table_filepath}")
        return
    elif len(table_filepaths) == 1:
        selected_table_filepath = table_filepaths[0]
    else:
        table_filenames = [filepath.name for filepath in table_filepaths]
        selected_table_filename = await questionary.select("Which table?", choices=table_filenames).ask_async()
        selected_table_filepath = INPUT_DIR / selected_table_filename

    worksheets = get_worksheets(selected_table_filepath)

    # TODO Показывать также количество строк в листах
    selected_worksheet_name = await questionary.select("Which worksheet?", choices=worksheets).ask_async()
    selected_worksheet = worksheets[selected_worksheet_name]
    table_data = excell.read_worksheet(selected_worksheet)

    print(f"Loaded {len(table_data)} rows from {selected_table_filepath.name} ({selected_worksheet_name})")
    async with AsyncSessionmaker() as session:
        for mint_account_data in table_data:
            group = mint_account_data["group"]
            invite_code = mint_account_data["mint"]["invite_code"]
            print(f"Group: '{group}'. Invite code: {invite_code}")

            wallet: LocalAccount = Wallet.from_key(mint_account_data["wallet"]["private_key"])
            wallet_defaults = {
                "private_key": wallet.key.hex().lower(),
                "address": wallet.address.lower(),
            }
            # db_wallet = await update_or_create(session, Wallet, wallet_defaults, address=wallet_defaults["address"])

            # Берем из бд или создаем кошелек
            db_wallet, _ = await get_or_create(session, Wallet, wallet_defaults, address=wallet_defaults["address"])
            print(f"\tWallet address: {wallet.address}")

            # По этому кошельку берем или создаем Mint аккаунт
            # здесь я использую update_or_create, чтобы можно было, изменив данные в таблице, изменить их и в бд
            mint_account_defaults = {
                "group": group,
                "invite_code": invite_code,
                "wallet": db_wallet,
            }
            db_mint_account, created = await update_or_create(
                session,
                MintAccount,
                mint_account_defaults,
                wallet=db_wallet,
            )
            if not created:
                await session.refresh(db_mint_account, attribute_names=["discord_account", "twitter_account"])

            if mint_account_data["proxy"]:
                proxy = BetterProxy.from_str(mint_account_data["proxy"])
                proxy_dict = proxy.model_dump()
                db_mint_account.proxy, created = await update_or_create(session, Proxy, proxy_dict, **proxy_dict)

                message = (f"\tProxy: "
                           f"[{db_mint_account.proxy.database_id}]"
                           f"{db_mint_account.proxy.better_proxy.fixed_length}")
                if created:
                    message += " (NEW!)"
                else:
                    pass
                print(message)

            # TODO Не стоит привязывать импортированные аккаунты-расходники (тви, дис) к определенном аккаунту
            #   Делать это стоит уже после того, как точно привязал их.
            #   Тогда придется изменить базу данных и сделать ее похоже на Таби.
            #   То есть из MintAccount стоит убрать twitter_database_id и discord_database_id

            # TODO Так как в процессе работы скрипта некоторые поля (auth_token, username, password) могут меняться,
            #   в таблице могут быть устаревшие данные.
            #   Поэтому перед импортом данных нужно спрашивать подтверждения у подтверждения у пользователя
            #   При повторном импорте может быть несколько ситуаций:
            #   - Аккаунт не был привязан до этого (тогда создаем и привязываем)
            #   - Этот аккаунт уже привязан к этому аккаунту (тогда спрашиваем, нужно ли обновить поля)
            #   - Этот аккаунт уже привязан к другому аккаунту (тогда спрашиваем, нужно ли перепривязать)
            #   Спршивать следует так:
            #   - Да
            #   - Да (для всех)
            #   - Нет
            #   - Нет (для всех)
            if (
                    (mint_account_data["twitter"]["auth_token"] or
                     mint_account_data["twitter"]["username"] or
                     mint_account_data["twitter"]["email"] or
                     mint_account_data["twitter"]["password"] or
                     mint_account_data["twitter"]["totp_secret"]) and
                    not db_mint_account.twitter_account
            ):
                db_mint_account.twitter_account = TwitterAccount(**mint_account_data["twitter"])

            if mint_account_data["discord"]["auth_token"] and not db_mint_account.discord_account:
                db_mint_account.discord_account = DiscordAccount(**mint_account_data["discord"])

            # Сохраняем привязанные к db_mint_account модели
            await session.commit()


async def select_and_process_group():
    async with AsyncSessionmaker() as session:
        # Запроса групп из бд
        groups = await get_groups(session)

        if not groups:
            print(f"Import accounts before!")
            return

        # Пользователь выбирает группы (хотя бы одну)
        while True:
            selected_groups = await questionary.checkbox("Select groups:", choices=groups).ask_async()

            if not selected_groups:
                print(f"Select at least one group!")
            else:
                break

        # Запрос аккаунтов выбранных групп
        mint_accounts = await get_accounts_by_groups(session, selected_groups)

    # run_forever = await questionary.confirm("Run forever?").ask_async()

    # if run_forever:
    #     print(f"Аккаунты равномерно распределены по суткам. Не выключайте скрипт.")

    for mint_account in mint_accounts:

        if mint_account.wallet.verification_failed:
            logger.warning(f"{mint_account} {mint_account.wallet} Wallet failed verification before")
            continue

        interacted = False

        retries = CONFIG.CONCURRENCY.MAX_RETRIES
        while retries > 0:
            try:
                # Функции будет вызываться повторно, если не произведен выход из цикла (break)

                mint_client = MintClient(mint_account)
                interacted |= await mint_client.login()
                interacted |= await mint_client.try_to_verify_wallet()
                interacted |= await mint_client.try_to_bind_twitter()
                interacted |= await mint_client.try_to_accept_invite()
                interacted |= await mint_client.complete_tasks()
                interacted |= await mint_client.claim_energy()
                interacted |= await mint_client.inject_all()

                break

            except (TwitterScriptError, DiscordScriptError) as exc:
                logger.warning(f"{mint_account} {exc}")
                break

            except (MintHTTPException, TwitterHTTPException, TwitterBadAccountError) as exc:
                # Повторные попытки на HTTP 5XX (ошибки на стороне сервера)
                if isinstance(exc, TwitterHTTPException):
                    if exc.response.status_code >= 500:
                        logger.warning(f"{mint_account} {exc}")
                    else:
                        logger.error(f"{mint_account} {exc}")
                        break

                if isinstance(exc, MintHTTPException):
                    if exc.response.status_code >= 500:
                        logger.warning(f"{mint_account} {exc}")
                    else:
                        logger.error(f"{mint_account} {exc}")
                        break

                logger.error(f"{mint_account} {exc}")
                break

            except requests.errors.RequestsError as exc:
                if exc.code in (23, 28, 35, 56, 7):
                    logger.warning(f"{mint_account} (May be bad or slow proxy) {exc}")
                else:
                    raise

            finally:
                sleep_time = randint(*CONFIG.CONCURRENCY.DELAY_BETWEEN_ACCOUNTS)
                if interacted and sleep_time > 0:
                    logger.info(f"{mint_account} Sleep {sleep_time} sec.")
                    await asyncio.sleep(sleep_time)

            retries -= 1
            if retries > 0:
                # Пауза перед следующей попыткой
                sleep_time = CONFIG.CONCURRENCY.DELAY_BETWEEN_RETRIES
                logger.warning(f"{mint_account}"
                               f" Не удалось завершить выполнение."
                               f" Повторная попытка через {sleep_time}s."
                               f" Осталось попыток: {retries}.")
                await asyncio.sleep(sleep_time)


MODULES = {
    '❌  Exit': exit,
    '➡️ Import xlsx table': select_and_import_table,
    '➡️ Select group and run': select_and_process_group,
}


async def select_module(modules) -> Callable:
    module_name = await questionary.select("Select module:", choices=list(modules.keys())).ask_async()
    return modules[module_name]


async def main():
    current_revision = await alembic_utils.get_current_revision()
    latest_revision = alembic_utils.get_latest_revision()
    if current_revision != latest_revision:
        print(
            f"Current revision is {current_revision}, but the latest revision is {latest_revision}."
            f" An update is required."
        )
        should_upgrade = await questionary.confirm(
            "Do you want to upgrade the database to the latest revision?"
        ).ask_async()

        if not should_upgrade:
            return

        await alembic_utils.upgrade()

    print_project_info()
    print_author_info()
    while True:
        module = await select_module(MODULES)

        await module()


if __name__ == "__main__":
    asyncio.run(main())
