from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class Sign(BaseModel):
    amount: int
    type: str


class User(BaseModel):
    id: int
    tree_id: Optional[int] = Field(None, alias="treeId")

    wallet_address: str = Field(..., alias="address")
    wallet_ens_address: Optional[str] = Field(None, alias="ens")

    me: int = Field(..., alias="energy")
    injected_me: int = Field(..., alias="tree")

    invite_id: Optional[int] = Field(None, alias="inviteId")
    invite_code: Optional[str] = Field(None, alias="code")
    invite_percent: Optional[int] = Field(None, alias="invitePercent")

    type: str
    nft_id: int = Field(..., alias="nft_id")
    nft_pass: int = Field(..., alias="nft_pass")

    stake_id: int = Field(..., alias="stake_id")
    signin: int
    twitter_id: Optional[int] = Field(None, alias="twitter")
    discord_id: Optional[int] = Field(None, alias="discord")
    status: str
    created_at: datetime = Field(alias="createdAt")
    signs: Optional[list[Sign]] = None

    @field_validator('created_at', mode="before")
    @classmethod
    def parse_created_at(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.split(".")[0])
        return v

    @field_validator('twitter_id', 'discord_id', mode="before")
    @classmethod
    def str_to_int(cls, v):
        return int(v) if v is not None and v.isdigit() else v


class Task(BaseModel):
    id: int
    name: str
    amount: int
    is_freeze: bool = Field(..., alias='isFreeze')
    spec: str
    claimed: bool | None = None


class Energy(BaseModel):
    uid: list[str]
    amount: int
    includes: list[int]
    type: str
    freeze: bool | None = None
