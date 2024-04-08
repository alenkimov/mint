from loguru import logger
from better_web3 import Chain
from web3.types import Wei, TxReceipt, HexStr
from eth_utils import from_wei

from ..config import CONFIG
from ..database import MintAccount
from .chains import sepolia, mintchain


def tx_hash_info(chain: Chain, account: MintAccount, tx_hash: HexStr | str, value: Wei | int = None) -> str:
    wallet = account.wallet.eth_account

    tx_hash_link = chain.tx_url(tx_hash)
    message = f"{account} [{wallet.address}] ({chain}) {tx_hash_link}"
    if value is not None:
        message += f"\n\tSent: {from_wei(value, 'ether')} {chain.native_currency.symbol}"
    return message


def tx_receipt_info(chain: Chain, account: MintAccount, tx_receipt: TxReceipt, value: Wei | int = None) -> str:
    wallet = account.wallet.eth_account

    tx_hash = tx_receipt.transactionHash.hex()
    message = tx_hash_info(chain, account, tx_hash, value)
    tx_fee_wei = tx_receipt.gasUsed * tx_receipt.effectiveGasPrice
    tx_fee = from_wei(tx_fee_wei, "ether")
    message += f"\n\tFee: {tx_fee} {chain.native_currency.symbol}"
    return message


async def wait_fot_tx_receipt(chain: Chain, account: MintAccount, tx_hash: HexStr, value: Wei | int = None) -> TxReceipt or None:
    wallet = account.wallet.eth_account

    if CONFIG.TRANSACTION.TIMEOUT <= 0:
        logger.success(tx_hash_info(chain, account, tx_hash, value=value))
        return

    logger.info(f"{account} [{wallet.address}] Waiting for tx. receipt {CONFIG.TRANSACTION.TIMEOUT} sec...")
    tx_receipt = await chain.wait_for_tx_receipt(tx_hash, CONFIG.TRANSACTION.TIMEOUT)
    logger.success(tx_receipt_info(chain, account, tx_receipt, value=value))


async def request_balances(account: MintAccount) -> tuple[Wei, Wei]:
    """
    :return: Sepilia and Mintchain $tETH balances
    """
    wallet = account.wallet.eth_account

    sepolia_balance_wei = await sepolia.get_balance(wallet.address)
    mintchain_balance_wei = await mintchain.get_balance(wallet.address)
    sepolia_balance_ether = from_wei(sepolia_balance_wei, 'ether')
    mintchain_balance_ether = from_wei(mintchain_balance_wei, 'ether')
    logger.info(f"{account} [{wallet.address}] Balances:"
                f"\n\t{sepolia.name}: {sepolia_balance_ether} ${sepolia.native_currency.symbol}"
                f"\n\t{mintchain.name}: {mintchain_balance_ether} ${mintchain.native_currency.symbol}")
    return sepolia_balance_wei, mintchain_balance_wei
