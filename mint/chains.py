from better_web3 import Chain, request_chains_data, chain_from_caip_2, CAIP2ChainData

from common.utils import load_toml

from .paths import CHAINS_TOML

LOCAL_CHAINS_CONFIG = load_toml(CHAINS_TOML)
CHAINS_CAIP2_DATA = request_chains_data()


def get_chain(chain_id: int) -> Chain:
    chain_data: CAIP2ChainData = CHAINS_CAIP2_DATA[chain_id]
    chain_config = LOCAL_CHAINS_CONFIG.get(str(chain_id), {})

    if "rpc" in chain_config:
        chain_data.rpc_list.insert(0, chain_config.pop("rpc"))

    return chain_from_caip_2(chain_data, **chain_config)


sepolia   = get_chain(11155111)
mintchain = get_chain(1686)
