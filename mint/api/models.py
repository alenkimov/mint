from typing import Any

from pydantic import BaseModel, Field


class Sign(BaseModel):
    amount: int
    type: str


class User(BaseModel):
    id: int
    tree_id: int | None = Field(..., alias='treeId')
    address: str
    ens: str | None = None
    energy: int
    tree: int
    invite_id: Any = Field(..., alias='inviteId')
    type: str
    stake_id: int
    nft_id: int
    nft_pass: int
    signin: int
    code: str | None = None
    twitter: str | None = None
    discord: str | None = None
    status: str
    created_at: str = Field(..., alias='createdAt')
    invite_percent: int | None = Field(None, alias='invitePercent')
    signs: list[Sign] | None = None


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
