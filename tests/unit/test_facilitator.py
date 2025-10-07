"""Unit tests for MockFacilitator."""

import pytest
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from facilitator import MockFacilitator
from x402_a2a.types import PaymentRequirements, PaymentPayload

logger = logging.getLogger(__name__)


class TestMockFacilitator:
    """Test suite for MockFacilitator."""

    def test_init_valid_settled(self, type_tracer):
        """Test facilitator initialization with valid=True, settled=True."""
        type_tracer.trace_call(
            "MockFacilitator.__init__",
            kwargs={'is_valid': True, 'is_settled': True}
        )

        facilitator = MockFacilitator(is_valid=True, is_settled=True)

        assert facilitator._is_valid is True
        assert facilitator._is_settled is True
        logger.info("✓ Facilitator initialized with valid=True, settled=True")

    def test_init_invalid(self, type_tracer):
        """Test facilitator initialization with valid=False."""
        type_tracer.trace_call(
            "MockFacilitator.__init__",
            kwargs={'is_valid': False, 'is_settled': False}
        )

        facilitator = MockFacilitator(is_valid=False, is_settled=False)

        assert facilitator._is_valid is False
        assert facilitator._is_settled is False
        logger.info("✓ Facilitator initialized with valid=False")

    def test_verify_valid_payment(self, type_tracer):
        """Test verify() with valid payment."""
        facilitator = MockFacilitator(is_valid=True, is_settled=True)

        # Create mock payment requirements
        requirements = PaymentRequirements(
            scheme="exact",
            network="base-sepolia",
            asset="0x036CbD53842c5426634e7929541eC2318f3dCF7e",
            pay_to="0xMerchant",
            max_amount_required="1000000",
            description="Test payment",
            resource="/test",
            mime_type="application/json",
            max_timeout_seconds=600
        )

        # Create mock payment payload
        payload = PaymentPayload(
            x402_version=1,
            scheme="exact",
            network="base-sepolia",
            payload={
                "signature": "0xTestSignature",
                "authorization": {
                    "from": "0xPayer",
                    "to": "0xMerchant",
                    "value": "1000000",
                    "valid_after": "0",
                    "valid_before": "9999999999",
                    "nonce": "0x123"
                }
            }
        )

        type_tracer.trace_call(
            "MockFacilitator.verify",
            kwargs={'payload': payload, 'requirements': requirements}
        )

        response = facilitator.verify(payload, requirements)

        type_tracer.trace_call(
            "MockFacilitator.verify",
            result=response
        )

        assert response.is_valid is True
        assert response.payer == "0xPayer"
        assert response.invalid_reason is None
        logger.info("✓ Valid payment verified successfully")

    def test_verify_invalid_payment(self, type_tracer):
        """Test verify() with invalid payment."""
        facilitator = MockFacilitator(is_valid=False, is_settled=False)

        requirements = PaymentRequirements(
            scheme="exact",
            network="base-sepolia",
            asset="0x036CbD53842c5426634e7929541eC2318f3dCF7e",
            pay_to="0xMerchant",
            max_amount_required="1000000",
            description="Test payment",
            resource="/test",
            mime_type="application/json",
            max_timeout_seconds=600
        )

        payload = PaymentPayload(
            x402_version=1,
            scheme="exact",
            network="base-sepolia",
            payload={
                "signature": "0xBadSignature",
                "authorization": {
                    "from": "0xPayer",
                    "to": "0xMerchant",
                    "value": "1000000",
                    "valid_after": "0",
                    "valid_before": "9999999999",
                    "nonce": "0x123"
                }
            }
        )

        response = facilitator.verify(payload, requirements)

        assert response.is_valid is False
        assert response.invalid_reason == "mock_invalid_payload"
        logger.info("✓ Invalid payment rejected correctly")

    def test_settle_successful(self, type_tracer):
        """Test settle() with successful settlement."""
        facilitator = MockFacilitator(is_valid=True, is_settled=True)

        requirements = PaymentRequirements(
            scheme="exact",
            network="base-sepolia",
            asset="0x036CbD53842c5426634e7929541eC2318f3dCF7e",
            pay_to="0xMerchant",
            max_amount_required="1000000",
            description="Test payment",
            resource="/test",
            mime_type="application/json",
            max_timeout_seconds=600
        )

        payload = PaymentPayload(
            x402_version=1,
            scheme="exact",
            network="base-sepolia",
            payload={
                "signature": "0xTestSignature",
                "authorization": {
                    "from": "0xPayer",
                    "to": "0xMerchant",
                    "value": "1000000",
                    "valid_after": "0",
                    "valid_before": "9999999999",
                    "nonce": "0x123"
                }
            }
        )

        response = facilitator.settle(payload, requirements)

        type_tracer.trace_call(
            "MockFacilitator.settle",
            result=response
        )

        assert response.success is True
        assert response.network == "base-sepolia"
        assert response.transaction.startswith("0xmock")
        assert response.error_reason is None
        logger.info("✓ Payment settled successfully")

    def test_settle_failed(self, type_tracer):
        """Test settle() with failed settlement."""
        facilitator = MockFacilitator(is_valid=True, is_settled=False)

        requirements = PaymentRequirements(
            scheme="exact",
            network="base-sepolia",
            asset="0x036CbD53842c5426634e7929541eC2318f3dCF7e",
            pay_to="0xMerchant",
            max_amount_required="1000000",
            description="Test payment",
            resource="/test",
            mime_type="application/json",
            max_timeout_seconds=600
        )

        payload = PaymentPayload(
            x402_version=1,
            scheme="exact",
            network="base-sepolia",
            payload={
                "signature": "0xTestSignature",
                "authorization": {
                    "from": "0xPayer",
                    "to": "0xMerchant",
                    "value": "1000000",
                    "valid_after": "0",
                    "valid_before": "9999999999",
                    "nonce": "0x123"
                }
            }
        )

        response = facilitator.settle(payload, requirements)

        assert response.success is False
        assert response.error_reason == "mock_settlement_failed"
        logger.info("✓ Failed settlement handled correctly")
