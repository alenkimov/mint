from better_web3 import Contract
from eth_typing import ChecksumAddress
from web3.types import Wei, Nonce, HexStr, TxReceipt
from eth_utils import to_checksum_address
from eth_account.account import LocalAccount
from web3.contract.async_contract import AsyncContractFunction

from common.utils import load_json

from .chains import sepolia, mintchain

from ..paths import ABI_DIR


class MintchainToEthBridge(Contract):
    DEFAULT_ABI = load_json(ABI_DIR / "mintchain_to_eth.json")
    DEFAULT_ADDRESS = to_checksum_address("0x4200000000000000000000000000000000000010")
    L2_TOKEN = to_checksum_address("0xdeaddeaddeaddeaddeaddeaddeaddeaddead0000")

    def _withdraw(
            self,
            *,
            amount: Wei | int,
            l2Token: ChecksumAddress = None,
            min_gas_limit: Wei | int = 0,
            extra_data: bytes = b""
    ) -> AsyncContractFunction:
        l2Token = l2Token or self.L2_TOKEN
        return self.functions.withdraw(l2Token, amount, min_gas_limit, extra_data)

    async def bridge(
            self,
            account: LocalAccount,
            value: Wei | int = None,
            **kwargs,
    ) -> HexStr:
        bridge_fn = self._withdraw(amount=value)
        return await self.chain.execute_fn(account, bridge_fn, value=value, **kwargs)


class EthToMintchainBridge(Contract):
    DEFAULT_ABI = load_json(ABI_DIR / "eth_to_mintchain_bridge.json")
    DEFAULT_ADDRESS = to_checksum_address("0xd9d4b3ad7edb8f852ab75afa66c1456c46fef210")

    def _deposit(
            self,
            l2_gas: Wei | int = 200_000,
            data: bytes = b"",
    ) -> AsyncContractFunction:
        return self.functions.depositETH(l2_gas, data)

    async def bridge(
            self,
            account: LocalAccount,
            value: float = None,
            **kwargs,
    ) -> HexStr:
        bridge_fn = self._deposit()
        return await self.chain.execute_fn(account, bridge_fn, value=value, **kwargs)


eth_to_mintchain_bridge = EthToMintchainBridge(sepolia)
mintchain_to_eth_bridge = MintchainToEthBridge(mintchain)
