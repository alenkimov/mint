from datetime import datetime

from pydantic import BaseModel, Field


class Sign(BaseModel):
    amount: int
    type: str


class User(BaseModel):
    id: int
    tree_id: int | None

    wallet_address: str
    wallet_ens_address: str | None

    me: int
    injected_me: int

    invite_id: int | None
    invite_code: str | None
    invite_percent: int | None

    type: str
    nft_id: int
    nft_pass: int

    stake_id: int
    signin: int
    twitter_id: int | None
    discord_id: int | None
    status: str
    created_at: str
    signs: list[Sign] | None = None

    @classmethod
    def from_raw_data(cls, data):
        created_at = data["createdAt"].split(".")[0]
        created_at = datetime.fromisoformat(created_at)
        values = {
            "id": data["id"],
            "tree_id": data["treeId"],
            "wallet_address": data["address"],
            "wallet_ens_address": data["ens"],
            "me": data["energy"],
            "injected_me": data["tree"],
            "invite_id": data["inviteId"],
            "invite_code": data["code"],
            "invite_percent": data["invitePercent"],
            "type": data["type"],
            "nft_id": data["nft_id"],
            "nft_pass": data["nft_pass"],
            "stake_id": data["stake_id"],
            "signin": data["signin"],
            "twitter_id": int(data["twitter"]),
            "discord_id": int(data["discord"]),
            "status": data["status"],
            "signs": data["signs"],
            "created_at": created_at,
        }
        return cls(**values)


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
