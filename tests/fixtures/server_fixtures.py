"""Server-related test fixtures."""

import pytest
import logging
import sys
import threading
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from merchant_server import MerchantServer
from facilitator import MockFacilitator


logger = logging.getLogger(__name__)


@pytest.fixture
def mock_facilitator():
    """
    Provide a mock payment facilitator.

    Returns:
        MockFacilitator: Configured to verify and settle all payments
    """
    logger.info("Creating MockFacilitator")
    facilitator = MockFacilitator(is_valid=True, is_settled=True)
    logger.debug(f"  facilitator_type: {type(facilitator).__name__}")
    logger.debug(f"  is_valid: {facilitator._is_valid}")
    logger.debug(f"  is_settled: {facilitator._is_settled}")
    return facilitator


@pytest.fixture
def merchant_server(mock_facilitator):
    """
    Provide a MerchantServer instance.

    Args:
        mock_facilitator: Injected facilitator fixture

    Returns:
        MerchantServer: Configured with test wallet and facilitator
    """
    logger.info("Creating MerchantServer")

    # Use valid checksummed Ethereum address for testing
    test_wallet = "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B"
    # Use port 5555 for integration tests (separate from default 5001)
    test_port = 5555

    logger.debug(f"  wallet_address: {test_wallet}")
    logger.debug(f"  port: {test_port} (integration test port)")

    # Override the facilitator in the server
    server = MerchantServer(wallet_address=test_wallet, port=test_port)
    server.payment_middleware.facilitator = mock_facilitator

    logger.info("MerchantServer created successfully")
    return server


@pytest.fixture
def running_server(merchant_server):
    """
    Provide a running MerchantServer in a background thread.

    Uses python-a2a's run_server() function to start Flask app.

    Args:
        merchant_server: Injected server fixture

    Yields:
        tuple: (server, base_url)
    """
    logger.info("Starting MerchantServer in background thread")

    port = merchant_server.port
    base_url = f"http://127.0.0.1:{port}"

    logger.debug(f"  base_url: {base_url}")

    # Import run_server from python-a2a
    from python_a2a import run_server

    # Create wrapper function for thread
    def start_server():
        run_server(merchant_server, host="127.0.0.1", port=port)

    # Start server in background thread
    server_thread = threading.Thread(
        target=start_server,
        daemon=True
    )
    server_thread.start()

    # Wait for server to be ready (longer wait for Flask startup)
    time.sleep(1.5)

    logger.info("Server started and ready")

    yield merchant_server, base_url

    logger.info("Test completed, server will be cleaned up")
