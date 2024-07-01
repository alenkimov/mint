from better_web3 import Chain, get_chain

from common.utils import load_toml

from ..paths import CHAINS_TOML

LOCAL_CHAINS_CONFIG = load_toml(CHAINS_TOML)


def _get_chain(chain_id: int) -> Chain:
    chain_config = LOCAL_CHAINS_CONFIG.get(str(chain_id), {})
    return get_chain(chain_id, **chain_config)


sepolia   = get_chain(11155111)
mintchain = get_chain(1686)

# sepolia = Chain('https://eth-sepolia.g.alchemy.com/v2/BQ43RWiHw-hqyM4NVLrzcYSm-ybT5tYN')
# mintchain = Chain('https://testnet-rpc.mintchain.io')
