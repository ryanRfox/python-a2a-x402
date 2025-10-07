"""
Mock Facilitator for x402 Payment Testing

Based on the reference implementation from a2a-x402/python/examples/adk-demo
Adapted to work with python-a2a (non-async)
"""

import logging
from typing import override

from x402_a2a.types import (
    ExactPaymentPayload,
    PaymentPayload,
    PaymentRequirements,
    SettleResponse,
    VerifyResponse,
)
from x402_a2a import FacilitatorClient

logger = logging.getLogger(__name__)


class MockFacilitator(FacilitatorClient):
    """
    A mock facilitator that bypasses real network calls for testing.

    In production, replace this with a real FacilitatorClient that connects
    to a payment facilitator service (e.g., Coinbase).

    Attributes:
        _is_valid: Whether verify() should return success (default: True)
        _is_settled: Whether settle() should return success (default: True)
    """

    def __init__(self, is_valid: bool = True, is_settled: bool = True):
        """
        Initialize the mock facilitator.

        Args:
            is_valid: If True, verify() returns success. If False, returns failure.
            is_settled: If True, settle() returns success. If False, returns failure.
        """
        self._is_valid = is_valid
        self._is_settled = is_settled
        logger.info(
            f"MockFacilitator initialized "
            f"(valid={is_valid}, settled={is_settled})"
        )

    @override
    def verify(
        self, payload: PaymentPayload, requirements: PaymentRequirements
    ) -> VerifyResponse:
        """
        Mock payment verification.

        In production, this would:
        1. Validate the EIP-3009 signature
        2. Check that authorization matches requirements
        3. Verify the payer has sufficient funds
        4. Return verification result

        Args:
            payload: Signed payment payload from client
            requirements: Original payment requirements from merchant

        Returns:
            VerifyResponse with is_valid and payer address
        """
        logger.info("=== MOCK FACILITATOR: VERIFY ===")
        logger.debug(f"Payload:\n{payload.model_dump_json(indent=2)}")
        logger.debug(f"Requirements:\n{requirements.model_dump_json(indent=2)}")

        payer = None

        # Extract payer from payload
        if isinstance(payload.payload, ExactPaymentPayload):
            payer = payload.payload.authorization.from_
            logger.info(f"Payer address: {payer}")
        else:
            raise TypeError(f"Unsupported payload type: {type(payload.payload)}")

        if self._is_valid:
            logger.info("✅ Payment VERIFIED")
            return VerifyResponse(is_valid=True, payer=payer)
        else:
            logger.warning("⛔ Payment INVALID")
            return VerifyResponse(is_valid=False, payer=payer, invalid_reason="mock_invalid_payload")

    @override
    def settle(
        self, payload: PaymentPayload, requirements: PaymentRequirements
    ) -> SettleResponse:
        """
        Mock payment settlement.

        In production, this would:
        1. Submit the EIP-3009 transfer to the blockchain
        2. Wait for transaction confirmation
        3. Return settlement result with transaction hash

        Args:
            payload: Signed payment payload
            requirements: Original payment requirements

        Returns:
            SettleResponse with success status and transaction hash
        """
        logger.info("=== MOCK FACILITATOR: SETTLE ===")

        if self._is_settled:
            # Generate a mock transaction hash
            tx_hash = "0xmock1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
            logger.info(f"✅ Payment SETTLED (tx: {tx_hash})")
            return SettleResponse(
                success=True,
                network=requirements.network,
                transaction=tx_hash
            )
        else:
            logger.warning("⛔ Settlement FAILED")
            return SettleResponse(
                success=False,
                errorReason="mock_settlement_failed"
            )
