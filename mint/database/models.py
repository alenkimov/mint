from typing import Annotated
from datetime import datetime

from functools import cached_property

from better_web3 import Wallet as BetterWallet
from better_proxy import Proxy as BetterProxy
from twitter.utils import hidden_value
import twitter

from common import discord


from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import ForeignKey
from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy import select
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncAttrs


Int_PK = Annotated[int, mapped_column(primary_key=True)]


class Base(AsyncAttrs, DeclarativeBase):
    pass


class TwitterUser(Base):
    __tablename__ = 'twitter_user'

    # fmt: off
    id:              Mapped[Int_PK]
    username:        Mapped[str | None] = mapped_column(String(100), unique=True)
    name:            Mapped[str | None] = mapped_column(String(50))
    description:     Mapped[str | None] = mapped_column(String(160))
    location:        Mapped[str | None] = mapped_column(String(30))
    created_at:      Mapped[datetime | None]
    followers_count: Mapped[int | None]
    friends_count:   Mapped[int | None]

    mint_user: Mapped["MintUser" or None] = relationship(back_populates="twitter_user")
    account: Mapped["TwitterAccount"]     = relationship(back_populates="user")
    # fmt: on

    def __repr__(self):
        return f"{self.__class__.__name__}(id={self.id}, username={self.username})"

    def __str__(self):
        return f"@{self.username} (id={self.id})" if self.username else f"(id={self.id})"


class TwitterAccount(Base):
    __tablename__ = 'twitter_account'

    # fmt: off
    database_id: Mapped[Int_PK]

    auth_token:  Mapped[str | None] = mapped_column(unique=True)
    ct0:         Mapped[str | None] = mapped_column(String(160), unique=True)
    username:    Mapped[str | None] = mapped_column(String(100), unique=True)
    password:    Mapped[str | None] = mapped_column(String(128))
    email:       Mapped[str | None] = mapped_column(String(254), unique=True)
    totp_secret: Mapped[str | None] = mapped_column(String(16), unique=True)
    backup_code: Mapped[str | None] = mapped_column(String(12), unique=True)
    status:      Mapped[twitter.AccountStatus] = mapped_column(default="UNKNOWN")

    bound_to_another_mint_user: Mapped[bool] = mapped_column(default=False)

    twitter_id: Mapped[int   | None] = mapped_column(ForeignKey("twitter_user.id"))
    user: Mapped[TwitterUser | None] = relationship(back_populates="account")

    mint_account: Mapped["MintAccount"] = relationship(back_populates="twitter_account")
    # fmt: on

    def __repr__(self):
        return f"{self.__class__.__name__}(database_id={self.database_id}, auth_token={self.hidden_auth_token}, username={self.username})"

    def __str__(self):
        return f"@{self.username} (database_id={self.database_id})" if self.username else f"(database_id={self.database_id})"

    @property
    def hidden_auth_token(self) -> str | None:
        return hidden_value(self.auth_token) if self.auth_token else None

    @property
    def bound(self) -> bool | None:
        """
        mint_account.mint_user, user.mint_user уже должны быть запрошены, иначе вернет None
        """
        if not self.mint_account:
            return None

        if not self.mint_account.mint_user:
            return None

        if not self.user:
            return None

        if not self.user.mint_user:
            return None

        return self.mint_account.mint_user != self.user.mint_user


class DiscordGuildJoinStatus(Base):
    __tablename__ = "discord_guild_join_status"
    __table_args__ = (PrimaryKeyConstraint("discord_id", "guild_id"),)

    discord_id:  Mapped[int] = mapped_column(ForeignKey("discord_account.id"))
    guild_id:    Mapped[int]
    invite_code: Mapped[str | None] = mapped_column(String(32))
    joined:      Mapped[bool]

    discord_account: Mapped["DiscordAccount"] = relationship(back_populates="guild_join_statuses")


class DiscordAccount(Base):
    __tablename__ = "discord_account"

    # fmt: off
    database_id: Mapped[Int_PK]
    id:          Mapped[int | None] = mapped_column(unique=True, index=True)
    username:    Mapped[str | None] = mapped_column(String(32))
    email:       Mapped[str | None] = mapped_column(String(254), unique=True)
    phone:       Mapped[str | None] = mapped_column(String(18))
    name:        Mapped[str | None] = mapped_column(String(32))

    auth_token:  Mapped[str | None] = mapped_column(unique=True)
    status: Mapped[discord.AccountStatus] = mapped_column(default="UNKNOWN")
    required_action: Mapped[discord.RequiredAction | None]

    bound_to_another_mint_user: Mapped[bool] = mapped_column(default=False)

    mint_user:    Mapped["MintUser" or None] = relationship(back_populates="discord_account")
    mint_account: Mapped["MintAccount"]      = relationship(back_populates="discord_account")

    guild_join_statuses: Mapped[list[DiscordGuildJoinStatus]] = relationship(back_populates="discord_account")
    # fmt: on

    def __repr__(self):
        return f"{self.__class__.__name__}(database_id={self.database_id}, id={self.id}, auth_token={self.hidden_auth_token}, username={self.username})"

    def __str__(self):
        return f"@{self.username} (id={self.id})" if self.username else f"(id={self.id})"

    @property
    def hidden_auth_token(self) -> str | None:
        return twitter.utils.hidden_value(self.auth_token) if self.auth_token else None

    @property
    def bound(self) -> bool | None:
        """
        mint_account уже должен быть запрошен, иначе вернет None
        """
        if not self.mint_user:
            return None

        if not self.mint_account:
            return None

        return self.mint_account.mint_user_id == self.mint_user.id

    async def joined_guild(self, guild_id: int, session: AsyncSession) -> bool | None:
        try:
            # Создаем асинхронный запрос на выборку
            async with session.begin():
                result = await session.execute(
                    select(DiscordGuildJoinStatus).where(
                        DiscordGuildJoinStatus.discord_id == self.id,
                        DiscordGuildJoinStatus.guild_id == guild_id
                    )
                )
                join_status = result.scalars().one()  # Получаем единственный результат или вызываем исключение
                return join_status.joined
        except NoResultFound:
            return None

    async def joined_mint_guild(self, session: AsyncSession) -> bool | None:
        return await self.joined_guild(1172040134355587092, session)


class Wallet(Base):
    __tablename__ = "wallet"

    # fmt: off
    private_key: Mapped[str] = mapped_column(String(66), unique=True)
    address:     Mapped[str] = mapped_column(String(42), primary_key=True)
    ens_address: Mapped[str | None] = mapped_column(String(251))

    verification_failed: Mapped[bool] = mapped_column(default=False)
    # fmt: on

    mint_user:    Mapped["MintUser" or None] = relationship(back_populates="wallet")
    mint_account: Mapped["MintAccount"]      = relationship(back_populates="wallet")

    @cached_property
    def better_wallet(self) -> BetterWallet:
        return BetterWallet.from_key(self.private_key)

    def __repr__(self):
        return f"{self.__class__.__name__}(address={self.address})"

    def __str__(self):
        return str(self.better_wallet)


class Proxy(Base):
    __tablename__ = "proxy"

    # fmt: off
    database_id: Mapped[Int_PK]

    host:     Mapped[str] = mapped_column(String(253))
    port:     Mapped[int]
    login:    Mapped[str] = mapped_column(String(32))
    password: Mapped[str] = mapped_column(String(128))
    protocol: Mapped[str] = mapped_column(String(10))

    mint_account: Mapped["MintAccount"] = relationship(back_populates="proxy")
    # fmt: on

    @cached_property
    def better_proxy(self) -> BetterProxy:
        return BetterProxy(
            host=self.host,
            port=self.port,
            login=self.login,
            password=self.password,
            protocol=self.protocol,
        )

    def __repr__(self):
        return f"{self.__class__.__name__}(database_id={self.database_id}, host={self.host}, port={self.port})"

    def __str__(self):
        return self.better_proxy.fixed_length


class MintUser(Base):
    __tablename__ = "mint_user"

    # fmt: off
    id:      Mapped[Int_PK]     = mapped_column()
    tree_id: Mapped[int | None] = mapped_column(unique=True)

    # Кошелек
    wallet_ens_address: Mapped[str    | None] = mapped_column(String(251))
    wallet_address:     Mapped[str]           = mapped_column(ForeignKey("wallet.address"))
    wallet:             Mapped[Wallet | None] = relationship(back_populates="mint_user")

    # Реферальная система
    inviter_user_id: Mapped[int | None] = mapped_column(ForeignKey("mint_user.id"))
    invite_code:     Mapped[str | None] = mapped_column(String(8), unique=True)
    invite_percent:  Mapped[int | None] = mapped_column()

    inviter:       Mapped["MintUser" or None] = relationship(back_populates="invited_users",
                                                             remote_side=[id])
    invited_users: Mapped[list["MintUser"]]   = relationship(back_populates="inviter")

    # ME (Energy)
    me:          Mapped[int]
    injected_me: Mapped[int]

    # Другое
    type:       Mapped[str] = mapped_column(String(100))
    stake_id:   Mapped[int]
    nft_id:     Mapped[int]
    nft_pass:   Mapped[int]
    signin:     Mapped[int]
    status:     Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime]
    # signs          = fields.JSONField(null=True)

    # Социальные сети
    twitter_id: Mapped[int | None] = mapped_column(ForeignKey("twitter_user.id"))
    discord_id: Mapped[int | None] = mapped_column(ForeignKey("discord_account.id"))
    twitter_user:    Mapped[TwitterUser    | None] = relationship(back_populates="mint_user")
    discord_account: Mapped[DiscordAccount | None] = relationship(back_populates="mint_user")

    # Связи
    mint_account:  Mapped["MintAccount" or None] = relationship(back_populates="user")
    # fmt: on

    def __repr__(self):
        return f"{self.__class__.__name__}(id={self.id}, wallet_address={self.wallet_address})"

    def __str__(self):
        return self.wallet_address


class MintAccount(Base):
    __tablename__ = "mint_account"

    # fmt: off
    database_id: Mapped[Int_PK]

    group:       Mapped[str | None] = mapped_column(String(16), index=True)
    name:        Mapped[str | None] = mapped_column(String(16))
    auth_token:  Mapped[str | None] = mapped_column(unique=True)
    invite_code: Mapped[str | None] = mapped_column(String(8))

    proxy_database_id:   Mapped[int | None] = mapped_column(ForeignKey("proxy.database_id"))
    mint_user_id:        Mapped[int | None] = mapped_column(ForeignKey("mint_user.id"))
    twitter_database_id: Mapped[int | None] = mapped_column(ForeignKey("twitter_account.database_id"))
    discord_database_id: Mapped[int | None] = mapped_column(ForeignKey("discord_account.database_id"))
    wallet_address:      Mapped[str]        = mapped_column(ForeignKey("wallet.address"))

    proxy:           Mapped[Proxy          | None] = relationship(back_populates="mint_account")
    user:            Mapped[MintUser       | None] = relationship(back_populates="mint_account")
    twitter_account: Mapped[TwitterAccount | None] = relationship(back_populates="mint_account")
    discord_account: Mapped[DiscordAccount | None] = relationship(back_populates="mint_account")
    wallet:          Mapped[Wallet]                = relationship(back_populates="mint_account")
    # fmt: on

    def __repr__(self):
        return f"{self.__class__.__name__}(database_id={self.database_id}, group={self.group})"

    def __str__(self):
        return f"[{self.database_id}]({self.group})" if self.group else f"[{self.database_id}]"
