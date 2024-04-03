from better_web3 import Contract
from eth_typing import ChecksumAddress
from web3.types import Wei, Nonce, HexStr, TxReceipt
from eth_utils import to_checksum_address
from eth_account.account import LocalAccount
from web3.contract.async_contract import AsyncContractFunction

from common.utils import load_json

from .paths import ABI_DIR


class MintchainToEthBridge(Contract):
    DEFAULT_ABI = load_json(ABI_DIR / "mintchain_to_eth.json")
    DEFAULT_ADDRESS = to_checksum_address("0x4200000000000000000000000000000000000007")
    BRIDGE_ADDRESS = to_checksum_address("0x4200000000000000000000000000000000000010")

    # def _bridge_fn(
    #         self,
    #         *,
    #         token: ChecksumAddress,
    #         sender: ChecksumAddress,
    #         target: ChecksumAddress,
    #         value: float,
    #         nonce: int,
    #         # message: bytes,
    #         min_gas_limit: Wei | int = 200_000,
    # ) -> AsyncContractFunction:
    #     return self.functions.relayMessage(nonce, sender, target, value, message, min_gas_limit)
    #
    # async def bridge(
    #         self,
    #         account: LocalAccount,
    #         value: Wei | int = None,
    #         **kwargs,
    # ) -> HexStr:
    #     target = self.BRIDGE_ADDRESS
    #     # message
    #     l2_token = to_checksum_address("0xdeaddeaddeaddeaddeaddeaddeaddeaddead0000")
    #     min_gas_limit = 0
    #     extra_data = b"0x"
    #     bridge_fn = self._bridge_fn()
    #     return await self.chain.execute_fn(account, bridge_fn, value=value, **kwargs)


class EthToMintchainBridge(Contract):
    DEFAULT_ABI = load_json(ABI_DIR / "eth_to_mintchain_bridge.json")
    DEFAULT_ADDRESS = to_checksum_address("0xd9d4b3ad7edb8f852ab75afa66c1456c46fef210")

    def _bridge_fn(
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
        bridge_fn = self._bridge_fn()
        return await self.chain.execute_fn(account, bridge_fn, value=value, **kwargs)
