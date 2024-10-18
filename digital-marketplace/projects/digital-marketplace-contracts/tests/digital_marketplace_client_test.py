import algokit_utils
import pytest
import algosdk
from algokit_utils import get_localnet_default_account
from algokit_utils.config import config
from algosdk.v2client.algod import AlgodClient
from algosdk.v2client.indexer import IndexerClient
from algokit_utils.beta.account_manager import AddressAndSigner
from algokit_utils.beta.algorand_client import (
    AlgorandClient,
    PayParams,
    AssetCreateParams,
)
from algosdk.atomic_transaction_composer import TransactionWithSigner
from smart_contracts.artifacts.digital_marketplace.digital_marketplace_client import DigitalMarketplaceClient

@pytest.fixture(scope='session')
def algorand() -> AlgorandClient:
    """Get an Algorand Client to be used throughout the tests"""
    return AlgorandClient.default_local_net()

@pytest.fixture(scope='session')
def dispenser(algorand: AlgorandClient) -> AddressAndSigner:
    """Get a dispenser for funding test accounts"""
    return algorand.account.dispenser()

@pytest.fixture(scope='session')
def seller(
    algorand: AlgorandClient, 
    dispenser: AddressAndSigner
) -> AddressAndSigner:
    """Get a seller account"""
    acc = algorand.account.random()
    fund_txn = PayParams(
        sender=dispenser.address,
        receiver=acc.address,
        amount=10_000_000
    )
    algorand.send.payment(fund_txn)

    return acc

@pytest.fixture(scope='session')
def buyer(algorand: AlgorandClient) -> AddressAndSigner:
    """Get a buyer account"""
    acc = algorand.account.random()
    fund_txn = PayParams(
        sender=dispenser.address,
        receiver=acc.address,
        amount=10_000_000
    )
    algorand.send.payment(fund_txn)
    
    return acc

@pytest.fixture(scope='session')
def test_asset_id(
    seller: AddressAndSigner,
    algorand: AlgorandClient
) -> int:
    asset_create_txn = AssetCreateParams(
        total=100,
        sender=seller.address,
    )

    txn_response = algorand.send.asset_create(asset_create_txn);

    return txn_response['confirmation']['asset-index']

@pytest.fixture(scope='session')
def digital_marketplace_client(
    seller: AddressAndSigner,
    algorand: AlgorandClient,
    test_asset_id: int,
) -> DigitalMarketplaceClient:
    """Create instance of market place contract client"""
    client = DigitalMarketplaceClient(
        algod_client=algorand.client.algod,
        sender=seller.address,
        signer=seller.signer
    )

    """Create app instance"""
    client.create_create_application(
        unitary_price=2_000_000,
        asset_id=test_asset_id
    )

    return client


def test_asset_create(
    test_asset_id: int
) -> None:
    assert test_asset_id > 0

def test_set_price(
    digital_marketplace_client: DigitalMarketplaceClient
) -> None:
    digital_marketplace_client.set_price(unitary_price=3_000_000)

    txn_response = digital_marketplace_client.get_price()
    assert txn_response.return_value == 3_000_000

def test_opt_in(
    digital_marketplace_client: DigitalMarketplaceClient,
    seller: AddressAndSigner,
    test_asset_id: int,
    algorand: AlgorandClient
) -> None:
    pytest.raises(
        algosdk.error.AlgodHTTPError,
        lambda: algorand.account.get_asset_information(
            digital_marketplace_client.app_address,
            test_asset_id
        )
    )

    mbr_pay = algorand.transactions.payment(
        PayParams(
            sender=seller.address,
            receiver=digital_marketplace_client.app_address,
            amount=200_000,
            extra_fee=1_000,
        )
    )

    result = digital_marketplace_client.optin_to_asset(
        mbr_txn=TransactionWithSigner(
            txn=mbr_pay, 
            signer=seller.signer
        ),
        transaction_parameters=algokit_utils.TransactionParameters(
            foreign_assets=[test_asset_id]
        )
    )

    asset_info = algorand.account.get_asset_information(
        digital_marketplace_client.app_address,
        test_asset_id
    )

    assert(asset_info['asset-holding']['amount'] == 0)