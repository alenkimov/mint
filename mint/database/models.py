from functools import cached_property

from better_web3 import Wallet as BetterWallet
from better_proxy import Proxy as BetterProxy
import twitter
from twitter.utils import hidden_value

from tortoise.models import Model
from tortoise import fields
from tortoise.exceptions import DoesNotExist

from common import discord

from .mixins import DatabaseIDMixin


# class Email(Model):
#     class Meta:
#         table = "email"
#
#     database_id = fields.IntField(pk=True)
#     email = fields.CharField(254, unique=True, null=True)


class TwitterUser(DatabaseIDMixin, Model):
    class Meta:
        table = "twitter_user"

    # fmt: off
    id              = fields.IntField(null=True, unique=True, index=True)
    username        = fields.CharField(100, null=True, unique=True)
    name            = fields.CharField(50, null=True)
    created_at      = fields.DatetimeField(null=True)
    description     = fields.CharField(160, null=True)
    location        = fields.CharField(30, null=True)
    followers_count = fields.IntField(null=True)
    friends_count   = fields.IntField(null=True)
    # fmt: on


class TwitterAccount(DatabaseIDMixin, Model):
    class Meta:
        table = "twitter_account"

    # fmt: off
    auth_token  = fields.CharField(40, unique=True, null=True)
    ct0         = fields.CharField(160, unique=True, null=True)
    password    = fields.CharField(128, null=True)
    email       = fields.CharField(254, unique=True, null=True)
    totp_secret = fields.CharField(16, unique=True, null=True)
    backup_code = fields.CharField(12, unique=True, null=True)
    status      = fields.CharEnumField(twitter.AccountStatus, default="UNKNOWN")

    bound_by_unknown_mint_user = fields.BooleanField(default=False)
    # fmt: on

    user = fields.OneToOneField(
        model_name="models.TwitterUser",
        related_name="account",
        source_field="twitter_user_database_id",
        to_field="database_id",
        null=True,
    )

    @property
    def hidden_auth_token(self) -> str | None:
        return hidden_value(self.auth_token) if self.auth_token else None

    def __str__(self):
        username = f"@{self.username}" if self.username else "USERNAME NOT REQUESTED"
        return f"[{self.hidden_auth_token}]({username})"

    def __repr__(self):
        return f"{self.__class__.__name__}(database_id={self.database_id}, auth_token={self.hidden_auth_token})"


class DiscordGuildJoinStatus(DatabaseIDMixin, Model):

    class Meta:
        table = "discord_guild_join_status"
        unique_together = (("discord_account", "guild_id"),)

    discord_account = fields.ForeignKeyField(
        model_name="models.DiscordAccount",
        related_name="guild_join_statuses",
        # source_field="discord_id",  # TODO Это не работает, так как в Tortoise ORM баг
        to_field="id",
    )
    guild_id    = fields.IntField()
    invite_code = fields.CharField(32, null=True)
    joined      = fields.BooleanField()


class DiscordAccount(DatabaseIDMixin, Model):
    class Meta:
        table = "discord_account"

    # fmt: off
    id         = fields.IntField(null=True, unique=True, index=True)
    username   = fields.CharField(32,  null=True, unique=True)
    email      = fields.CharField(254, null=True, unique=True)
    phone      = fields.CharField(18,  null=True)
    name       = fields.CharField(32,  null=True)

    auth_token      = fields.CharField(72, unique=True)
    status          = fields.CharEnumField(discord.AccountStatus, default="UNKNOWN")
    required_action = fields.CharEnumField(discord.RequiredAction)

    bound_by_unknown_mint_account = fields.BooleanField(default=False)
    # fmt: on

    @property
    def hidden_auth_token(self) -> str | None:
        return twitter.utils.hidden_value(self.auth_token) if self.auth_token else None

    async def joined_guild(self, guild_id: int) -> bool | None:
        try:
            join_status = await DiscordGuildJoinStatus.get(discord_id=self.id, guild_id=guild_id)
            return join_status.joined
        except DoesNotExist:
            return None

    async def joined_mint_guild(self) -> bool | None:
        return await self.joined_guild(1172040134355587092)

    def __str__(self):
        username = f"@{self.username}" if self.username else "USERNAME NOT REQUESTED"
        return f"[{self.hidden_auth_token}]({username})"

    def __repr__(self):
        return f"{self.__class__.__name__}(database_id={self.database_id}, auth_token={self.hidden_auth_token})"


class Wallet(Model):
    class Meta:
        table = "wallet"

    # fmt: off
    private_key = fields.CharField(66, pk=True)
    address     = fields.CharField(42, unique=True, index=True)
    # ens_address = fields.CharField(251, unique=True, index=True)
    # fmt: on

    async def save(self, *args, **kwargs):
        self.address = self.address.lower()
        self.private_key = self.private_key.lower()
        await super().save(*args, **kwargs)

    @cached_property
    def better_wallet(self) -> BetterWallet:
        return BetterWallet.from_key(self.private_key)


class Proxy(DatabaseIDMixin, Model):
    class Meta:
        table = "proxy"

    # fmt: off
    host     = fields.CharField(max_length=253)
    port     = fields.IntField()
    login    = fields.CharField(max_length=32)
    password = fields.CharField(max_length=128)
    protocol = fields.CharField(max_length=10)
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

    def __str__(self):
        return self.better_proxy.fixed_length


class MintUser(DatabaseIDMixin, Model):
    class Meta:
        table = "mint_user"

    # fmt: off
    id             = fields.IntField(unique=True, index=True)
    tree_id        = fields.IntField(unique=True)

    wallet_ens_address = fields.CharField(251, unique=True)

    invite_id      = fields.IntField(unique=True)
    invite_code    = fields.CharField(8, unique=True)
    invite_percent = fields.IntField()

    me             = fields.IntField()
    injected_me    = fields.IntField()

    type           = fields.CharField(100)
    stake_id       = fields.IntField(unique=True)
    nft_id         = fields.IntField(unique=True)
    nft_pass       = fields.IntField()
    signin         = fields.IntField()
    status         = fields.CharField(100)
    created_at     = fields.DatetimeField()
    # signs          = fields.JSONField(null=True)

    # fmt: on

    twitter_user = fields.OneToOneField(
        model_name="models.TwitterUser",
        related_name="mint_user",
        source_field="twitter_id",
        to_field="id",
        null=True,
    )
    discord_account = fields.OneToOneField(
        model_name="models.DiscordAccount",
        related_name="mint_user",
        source_field="discord_id",
        to_field="id",
        null=True,
    )
    wallet = fields.OneToOneField(
        model_name="models.Wallet",
        related_name="mint_user",
        source_field="wallet_address",
        to_field="address",
        null=True,
    )

    def __repr__(self):
        return f"{self.__class__.__name__}(database_id={self.database_id})"


class MintAccount(DatabaseIDMixin, Model):
    class Meta:
        table = "mint_account"

    # fmt: off
    name        = fields.CharField(32, null=True)
    group_name  = fields.CharField(32, index=True, null=True)

    auth_token = fields.CharField(177, unique=True)

    referrer_invite_code = fields.CharField(8)
    # fmt: on

    user = fields.OneToOneField(
        model_name="models.MintUser",
        related_name="account",
        source_field="mint_user_database_id",
        to_field="database_id",
    )
    proxy = fields.ForeignKeyField(
        model_name='models.Proxy',
        related_name='accounts',
        source_field="proxy_database_id",
        to_field='database_id',
        null=True,
    )

    def __str__(self):
        name = self.name or "NO NAME"
        proxy_representation = self.proxy.better_proxy.fixed_length or "[NO PROXY]"
        return f"{proxy_representation}[{self.database_id}]({name})"

    def __repr__(self):
        return f"{self.__class__.__name__}(database_id={self.database_id})"
