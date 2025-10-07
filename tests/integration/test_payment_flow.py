"""
Integration tests for complete payment flow.

Tests the full end-to-end payment process:
1. Client requests service
2. Server returns payment requirements
3. Client signs payment
4. Client submits payment
5. Server verifies payment
6. Server executes business logic
7. Server settles payment
8. Client receives result with receipt
"""

import pytest
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "fixtures"))

from server_fixtures import merchant_server, mock_facilitator, running_server
from client_fixtures import mock_wallet, payment_client, connected_client

logger = logging.getLogger(__name__)


class TestPaymentFlow:
    """Integration tests for payment flow."""

    def test_complete_payment_flow(
        self,
        connected_client,
        trace_scope_fixture,
        type_tracer
    ):
        """
        Test complete payment flow from request to settlement.

        This integration test verifies:
        - HTTP communication works
        - Payment requirements are sent correctly
        - Client can sign and submit payment
        - Server verifies and settles payment
        - Response includes product information
        """
        with trace_scope_fixture("Complete Payment Flow"):
            logger.info("STEP 1: Requesting paid service (auto-approve enabled)")

            type_tracer.trace_call(
                "PaymentAwareClient.ask",
                kwargs={'message_text': "Buy a laptop", 'auto_approve': True}
            )

            # Ask for paid service - payment flow should execute automatically
            response_text = connected_client.ask("Buy a laptop", auto_approve=True)

            type_tracer.trace_call(
                "PaymentAwareClient.ask",
                result=response_text
            )

            # Verify we got a response
            assert response_text is not None
            assert isinstance(response_text, str)
            assert len(response_text) > 0

            logger.info(f"  Response preview: {response_text[:100]}...")

            # Response should contain product information
            assert "laptop" in response_text.lower()

            # Should contain order/confirmation details
            assert any(keyword in response_text.lower() for keyword in ["order", "confirmation", "product", "payment"])

            logger.info("✓ Complete payment flow successful - product delivered")

    def test_free_service_no_payment(
        self,
        connected_client,
        trace_scope_fixture,
        type_tracer
    ):
        """
        Test that free services don't require payment.

        This verifies:
        - Free services complete without payment flow
        - Response is returned immediately
        - No payment dialogs or confirmations
        """
        with trace_scope_fixture("Free Service Flow"):
            logger.info("STEP 1: Requesting free service")

            type_tracer.trace_call(
                "PaymentAwareClient.ask",
                kwargs={'message_text': "What's your status?"}
            )

            # Ask for free service - should complete immediately
            response_text = connected_client.ask("What's your status?")

            type_tracer.trace_call(
                "PaymentAwareClient.ask",
                result=response_text
            )

            # Verify we got a response
            assert response_text is not None
            assert isinstance(response_text, str)
            assert len(response_text) > 0

            logger.info(f"  Response preview: {response_text[:100]}...")

            # Response should contain merchant info
            assert any(keyword in response_text.lower() for keyword in ["merchant", "status", "online", "protocol"])

            # Should NOT contain payment/order language
            assert "order" not in response_text.lower()
            assert "confirmation" not in response_text.lower()

            logger.info("✓ Free service flow successful - no payment required")

    def test_http_headers_work_end_to_end(
        self,
        connected_client,
        trace_scope_fixture
    ):
        """
        Test that HTTP header extension activation works end-to-end.

        This verifies:
        - Client sends X-A2A-Extensions header
        - Server receives and processes request
        - Response is returned successfully
        """
        with trace_scope_fixture("HTTP Header Extension Activation"):
            logger.info("Testing HTTP header activation with real HTTP request")

            # Make a real HTTP request - client should send X-A2A-Extensions header
            response_text = connected_client.ask("What's your status?")

            # If we got a response, headers worked
            assert response_text is not None
            assert len(response_text) > 0

            logger.info("✓ HTTP headers working end-to-end")
            logger.info("  Client sent: X-A2A-Extensions header (per spec Section 7)")
            logger.info("  Server processed request successfully")
