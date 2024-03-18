import asyncio
from typing import Callable
from random import randint

from tortoise import Tortoise, run_async
from better_web3 import Wallet as BetterWallet
from better_proxy import Proxy as BetterProxy

import questionary

from common import print_project_info, print_author_info, setup_logger
from common.excell import get_xlsx_filepaths, get_worksheets

from mint.paths import INPUT_DIR, DATABASE_FILEPATH, LOG_DIR
from mint.config import CONFIG
from mint.excell import excell
from mint.client import Client as MintClient
from mint.scripts import try_to_bind_twitter, try_to_invite
from mint.database import (
    get_accounts_by_groups,
    get_groups, MintAccount,
    DiscordAccount,
    TwitterAccount,
    Proxy,
    Wallet,
    TwitterUser,
)


setup_logger(LOG_DIR, CONFIG.LOGGING.LEVEL)


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

    selected_worksheet_name = await questionary.select("Which worksheet?", choices=worksheets).ask_async()
    selected_worksheet = worksheets[selected_worksheet_name]
    table_data = excell.read_worksheet(selected_worksheet)

    print(f"Loaded {len(table_data)} rows from {selected_table_filepath.name} ({selected_worksheet_name})")
    for mint_account_data in table_data:
        group_name = mint_account_data["group_name"]
        name = mint_account_data["name"]
        invite_code = mint_account_data["mint"]["invite_code"]
        print(f"Group: {group_name}. Account name: {name}. Invite code: {invite_code}")

        wallet = BetterWallet.from_key(mint_account_data["wallet"]["private_key"])
        db_wallet, _ = await Wallet.update_or_create(private_key=wallet.private_key.lower(),
                                                     address=wallet.address.lower())
        print(f"\tWallet address: {wallet.address}")

        db_mint_account, _ = await MintAccount.update_or_create(
            group_name=group_name,
            name=name,
            invite_code=invite_code,
            wallet=db_wallet,
        )

        if mint_account_data["proxy"]:
            proxy = BetterProxy.from_str(mint_account_data["proxy"])
            db_mint_account.proxy, _ = await Proxy.update_or_create(**proxy.model_dump())
            print(f"\tProxy: {proxy.fixed_length}")

        if (
                mint_account_data["twitter"]["auth_token"] or
                mint_account_data["twitter"]["username"] or
                mint_account_data["twitter"]["email"] or
                mint_account_data["twitter"]["password"] or
                mint_account_data["twitter"]["totp_secret"]
        ):
            username = mint_account_data["twitter"].pop("username")

            db_mint_account.twitter_account, _ = await TwitterAccount.update_or_create(**mint_account_data["twitter"])
            if username:
                db_mint_account.twitter_account.user, _ = await TwitterUser.update_or_create(username=username)

        if mint_account_data["discord"]["auth_token"]:
            db_mint_account.discord_account, _ = await DiscordAccount.update_or_create(**mint_account_data["discord"])

        await db_mint_account.save()


async def select_and_process_group():
    # Запроса групп из бд
    groups = await get_groups()

    if not groups:
        print(f"Import accounts before!")

    # Пользователь выбирает группы (хотя бы одну)
    while True:
        selected_groups = await questionary.checkbox("Select groups:", choices=groups).ask_async()

        if not selected_groups:
            print(f"Select at least one group!")
        else:
            break

    # Запрос аккаунтов выбранных групп
    mint_accounts = await get_accounts_by_groups(selected_groups)

    # Прогон аккаунтов
    for mint_account in mint_accounts:
        mint_client = MintClient(mint_account)
        await mint_client.login()
        await try_to_bind_twitter(mint_client)
        await try_to_invite(mint_client)
        await mint_client.complete_tasks()
        await mint_client.claim_energy()
        await mint_client.inject_all()

        await asyncio.sleep(randint(**CONFIG.CONCURRENCY.DELAY_BETWEEN_ACCOUNTS))


MODULES = {
    '❌  Exit': exit,
    '➡️ Import xlsx table': select_and_import_table,
    '➡️ Select group and run': select_and_process_group,
}


async def select_module(modules) -> Callable:
    module_name = await questionary.select("Select module:", choices=list(modules.keys())).ask_async()
    return modules[module_name]


async def main():
    await Tortoise.init(
        db_url=DATABASE_URL,
        modules={"models": ["mint.database.models"]},
    )
    await Tortoise.generate_schemas()

    while True:
        print_project_info()
        print_author_info()
        module = await select_module(MODULES)

        await module()


if __name__ == "__main__":
    run_async(main())
