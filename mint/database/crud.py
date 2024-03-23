from typing import Type, TypeVar

from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from .models import MintAccount


T = TypeVar('T')  # Для поддержки типизации возвращаемого значения функции


async def get_or_create(session: AsyncSession, model: Type[T], defaults: dict, **kwargs) -> tuple[T, bool]:
    query = select(model).filter_by(**kwargs)
    instance = await session.scalar(query)

    created = False
    if not instance:
        instance = model(**defaults)
        session.add(instance)
        await session.commit()
        created = True

    return instance, created


async def update_or_create(session: AsyncSession, model: Type[T], defaults: dict, **kwargs) -> tuple[T, bool]:
    """
    Асинхронно обновляет существующую запись в базе данных или создает новую, если она не найдена.

    :param session: Экземпляр асинхронной сессии SQLAlchemy.
    :param model: Класс модели, с которым будет проводиться операция.
    :param defaults: Словарь со значениями, которые будут использоваться для обновления или создания записи.
    :param kwargs: Поля и их значения, используемые для поиска существующей записи.
    :return: Объект модели, который был обновлен или создан. Был ли создан: True or False
    """
    query = select(model).filter_by(**kwargs)
    instance = await session.scalar(query)

    created = False
    if instance:
        for key, value in defaults.items():
            setattr(instance, key, value)
        await session.commit()
    else:
        instance = model(**defaults)
        session.add(instance)
        await session.commit()
        created = True

    return instance, created


async def get_groups(session: AsyncSession) -> set[str]:
    query = select(func.lower(MintAccount.group))
    groups = set(await session.scalars(query))
    return groups


async def get_accounts_by_groups(session: AsyncSession, groups: list[str]) -> list[MintAccount]:
    # Приведение имен групп к нижнему регистру
    groups = [group.lower() for group in groups]

    # Запрос аккаунтов с предзагрузкой всех необходимых связей
    query = select(MintAccount).options(
        joinedload(MintAccount.wallet),
        joinedload(MintAccount.proxy),
        joinedload(MintAccount.user),
        joinedload(MintAccount.twitter_account),
        joinedload(MintAccount.discord_account),
        # joinedload(MintAccount.twitter_account.user),
        # joinedload(MintAccount.user.wallet),
        # joinedload(MintAccount.user.twitter_user),
        # joinedload(MintAccount.user.discord_account),
    ).filter(func.lower(MintAccount.group).in_(groups))

    accounts = list(await session.scalars(query))
    return accounts
