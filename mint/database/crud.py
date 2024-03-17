from tortoise.functions import Lower

from .models import MintAccount


async def get_groups() -> set[str]:
    groups = await MintAccount.annotate(lower_group_name=Lower("group_name")).values_list("lower_group_name", flat=True)
    return {group if group else "no_group" for group in groups}


async def get_accounts_by_groups(groups: list[str]) -> list[MintAccount]:
    # Приведение имен групп к нижнему регистру, если это необходимо
    groups = [group.lower() for group in groups]

    # Запрос аккаунтов, группа которых совпадает с одной из выбранных
    return await MintAccount.annotate(lower_group_name=Lower("group_name")).filter(lower_group_name__in=groups)