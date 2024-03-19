from tortoise.functions import Lower

from .models import MintAccount


async def get_groups() -> set[str]:
    groups = await MintAccount.annotate(lower_group_name=Lower("group_name")).values_list("lower_group_name", flat=True)
    return {group if group else "no_group" for group in groups}


# async def get_accounts_by_groups(groups: list[str]) -> list[MintAccount]:
#     # Приведение имен групп к нижнему регистру, если это необходимо
#     groups = [group.lower() for group in groups]
#
#     # Запрос аккаунтов, группа которых совпадает с одной из выбранных
#     return await MintAccount.annotate(lower_group_name=Lower("group_name")).filter(lower_group_name__in=groups).prefetch_related()

async def get_accounts_by_groups(groups: list[str]) -> list[MintAccount]:
    # Приведение имен групп к нижнему регистру
    groups = [group.lower() for group in groups]

    # Запрос аккаунтов с предзагрузкой всех необходимых связей
    return await MintAccount.annotate(
        lower_group_name=Lower("group_name")
    ).filter(
        lower_group_name__in=groups
    ).prefetch_related(
        'discord_account',
        'twitter_account',
        'twitter_account__user',
        'wallet',
        'proxy',
        'user',
        'user__wallet',
        'user__twitter_user',
        'user__discord_account',
    ).all()
