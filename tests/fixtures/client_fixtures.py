"""Client-related test fixtures."""

import pytest
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from payment_client import PaymentAwareClient
from wallet import MockLocalWallet


logger = logging.getLogger(__name__)


@pytest.fixture
def mock_wallet():
    """
    Provide a mock wallet for testing.

    Returns:
        MockLocalWallet: Test wallet with known address
    """
    logger.info("Creating MockLocalWallet")
    wallet = MockLocalWallet()
    logger.debug(f"  wallet_address: {wallet.address}")
    logger.debug(f"  wallet_type: {type(wallet).__name__}")
    return wallet


@pytest.fixture
def payment_client(mock_wallet):
    """
    Provide a PaymentAwareClient instance.

    Args:
        mock_wallet: Injected wallet fixture

    Returns:
        PaymentAwareClient: Client configured with mock wallet
    """
    logger.info("Creating PaymentAwareClient")

    # We'll set the endpoint_url when actually using the client
    # For now, use a placeholder
    placeholder_url = "http://placeholder:5000"

    client = PaymentAwareClient(
        endpoint_url=placeholder_url,
        wallet=mock_wallet
    )

    logger.debug(f"  client_type: {type(client).__name__}")
    logger.debug(f"  wallet_address: {client.wallet.address}")
    logger.info("PaymentAwareClient created successfully")

    return client


@pytest.fixture
def connected_client(mock_wallet, running_server):
    """
    Provide a client connected to a running server.

    Args:
        mock_wallet: Injected wallet fixture
        running_server: Injected running server fixture

    Returns:
        PaymentAwareClient: Client connected to test server
    """
    server, base_url = running_server

    logger.info("Configuring client for running server")
    logger.debug(f"  server_url: {base_url}")

    # Create new client with actual server URL
    client = PaymentAwareClient(
        endpoint_url=base_url,
        wallet=mock_wallet
    )

    logger.info("Client connected to server")
    return client
