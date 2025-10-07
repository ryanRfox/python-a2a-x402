"""Unit tests for MockLocalWallet."""

import pytest
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from wallet import MockLocalWallet
from x402_a2a import create_payment_requirements

logger = logging.getLogger(__name__)


class TestMockLocalWallet:
    """Test suite for MockLocalWallet."""

    def test_init(self, type_tracer):
        """Test wallet initialization."""
        type_tracer.trace_call("MockLocalWallet.__init__")

        wallet = MockLocalWallet()

        type_tracer.trace_call(
            "MockLocalWallet.__init__",
            result={'address': wallet.address}
        )

        assert wallet.address.startswith("0x")
        assert len(wallet.address) == 42  # Ethereum address length
        logger.info(f"✓ Wallet initialized with address: {wallet.address}")

    def test_sign_payment(self, type_tracer):
        """Test payment signing."""
        wallet = MockLocalWallet()

        # Use create_payment_requirements to get proper EIP-712 domain
        # Use a valid checksummed Ethereum address
        requirements = create_payment_requirements(
            price="$5.00",  # Will be converted to atomic USDC amount
            pay_to_address="0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
            resource="/products/test",
            network="base-sepolia",
            description="Test product"
        )

        type_tracer.trace_call(
            "MockLocalWallet.sign_payment",
            kwargs={'requirements': requirements}
        )

        payment_payload = wallet.sign_payment(requirements)

        type_tracer.trace_call(
            "MockLocalWallet.sign_payment",
            result=payment_payload
        )

        # Verify payment payload structure
        assert payment_payload.x402_version == 1
        assert payment_payload.scheme == "exact"
        assert payment_payload.network == "base-sepolia"

        # Verify authorization data
        auth = payment_payload.payload.authorization
        assert auth.from_ == wallet.address
        assert auth.to == "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B"
        # Value will be atomic USDC amount for $5.00

        # Verify signature exists
        assert payment_payload.payload.signature.startswith("0x")
        assert len(payment_payload.payload.signature) > 10

        logger.info("✓ Payment signed successfully")
        logger.debug(f"  Signature: {payment_payload.payload.signature[:20]}...")

    def test_sign_payment_amount_validation(self):
        """Test that signed payment respects max_amount_required."""
        wallet = MockLocalWallet()

        requirements = create_payment_requirements(
            price="$1.00",
            pay_to_address="0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
            resource="/test",
            network="base-sepolia",
            description="Test"
        )

        payload = wallet.sign_payment(requirements)

        # Verify amount does not exceed max_amount_required
        assert int(payload.payload.authorization.value) <= int(
            requirements.max_amount_required
        )
        logger.info("✓ Payment amount validation successful")

    def test_sign_payment_network_consistency(self):
        """Test that signed payment matches network from requirements."""
        wallet = MockLocalWallet()

        for network in ["base-sepolia", "base"]:
            requirements = create_payment_requirements(
                price="$1.00",
                pay_to_address="0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
                resource="/test",
                network=network,
                description="Test"
            )

            payload = wallet.sign_payment(requirements)

            assert payload.network == network
            logger.info(f"✓ Network consistency verified for: {network}")
