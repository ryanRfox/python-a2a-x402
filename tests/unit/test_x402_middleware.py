"""Unit tests for x402PaymentMiddleware."""

import pytest
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from x402_middleware import x402PaymentMiddleware
from facilitator import MockFacilitator
from x402_a2a.types import (
    PaymentRequirements,
    PaymentPayload,
    x402PaymentRequiredException
)
from python_a2a import Task, TaskStatus, TaskState, Message, TextContent, MessageRole

logger = logging.getLogger(__name__)


class TestX402PaymentMiddleware:
    """Test suite for x402PaymentMiddleware."""

    def test_init(self, type_tracer, mock_facilitator):
        """Test middleware initialization."""
        type_tracer.trace_call(
            "x402PaymentMiddleware.__init__",
            kwargs={'facilitator': mock_facilitator}
        )

        middleware = x402PaymentMiddleware(facilitator=mock_facilitator)

        type_tracer.trace_call(
            "x402PaymentMiddleware.__init__",
            result=middleware
        )

        assert middleware.facilitator == mock_facilitator
        assert middleware.payment_store == {}
        logger.info("✓ Middleware initialized successfully")

    def test_wrap_business_logic_no_exception(self, type_tracer, mock_facilitator):
        """Test wrapping business logic that doesn't require payment."""
        middleware = x402PaymentMiddleware(facilitator=mock_facilitator)

        # Business logic that returns normally
        def free_service(task: Task) -> Task:
            task.status = TaskStatus(state=TaskState.COMPLETED)
            task.artifacts = [{
                "parts": [{"type": "text", "text": "Here's your free info"}]
            }]
            return task

        # Create task
        message = Message(
            content=TextContent(text="Get free info"),
            role=MessageRole.USER
        )
        task = Task(
            message=message.to_dict()
        )

        type_tracer.trace_call(
            "x402PaymentMiddleware.process_task",
            kwargs={'business_logic': free_service, 'task': task}
        )

        # Process task with middleware
        result = middleware.process_task(task, free_service)

        type_tracer.trace_call(
            "x402PaymentMiddleware.process_task",
            result=result
        )

        assert result.status.state == TaskState.COMPLETED
        logger.info("✓ Free service passed through without payment")

    def test_wrap_catches_payment_exception(self, type_tracer, mock_facilitator):
        """Test middleware catches x402PaymentRequiredException."""
        middleware = x402PaymentMiddleware(facilitator=mock_facilitator)

        # Business logic that requires payment
        def paid_service(task: Task) -> Task:
            requirements = PaymentRequirements(
                scheme="exact",
                network="base-sepolia",
                asset="0x036CbD53842c5426634e7929541eC2318f3dCF7e",
                pay_to="0xMerchant",
                max_amount_required="5000000",
                description="Test product",
                resource="/product/test",
                mime_type="application/json",
                max_timeout_seconds=600
            )
            raise x402PaymentRequiredException(
                "Payment required",
                payment_requirements=[requirements]
            )

        # Create task
        message = Message(
            content=TextContent(text="Buy product"),
            role=MessageRole.USER
        )
        task = Task(
            message=message.to_dict()
        )

        type_tracer.trace_call(
            "x402PaymentMiddleware.process_task",
            kwargs={'business_logic': paid_service, 'task': task}
        )

        # Process task with middleware
        result = middleware.process_task(task, paid_service)

        type_tracer.trace_call(
            "x402PaymentMiddleware.process_task",
            result=result
        )

        # Should return payment required response
        assert result.status.state == TaskState.INPUT_REQUIRED
        assert result.status.message is not None

        # Check metadata - status.message is a dict from Message.to_dict()
        status_message_dict = result.status.message
        metadata = status_message_dict.get('metadata', {})
        custom_fields = metadata.get('custom_fields', metadata)
        assert "x402.payment.status" in custom_fields
        assert custom_fields["x402.payment.status"] == "payment-required"

        logger.info("✓ Payment exception caught and converted to payment-required response")

    def test_verify_and_settle_flow(self, type_tracer, mock_facilitator):
        """Test payment verification and settlement flow."""
        # Create payment requirements
        requirements = PaymentRequirements(
            scheme="exact",
            network="base-sepolia",
            asset="0x036CbD53842c5426634e7929541eC2318f3dCF7e",
            pay_to="0xMerchant",
            max_amount_required="5000000",
            description="Test product",
            resource="/product/test",
            mime_type="application/json",
            max_timeout_seconds=600
        )

        # Create payment payload (simplified for testing)
        payload = PaymentPayload(
            x402_version=1,
            scheme="exact",
            network="base-sepolia",
            payload={
                "signature": "0xTestSignature",
                "authorization": {
                    "from": "0xPayer",
                    "to": "0xMerchant",
                    "value": "5000000",
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

        # Verify payment
        verify_response = mock_facilitator.verify(payload, requirements)

        type_tracer.trace_call(
            "MockFacilitator.verify",
            result=verify_response
        )

        assert verify_response.is_valid is True
        assert verify_response.payer is not None

        type_tracer.trace_call(
            "MockFacilitator.settle",
            kwargs={'payload': payload, 'requirements': requirements}
        )

        # Settle payment
        settle_response = mock_facilitator.settle(payload, requirements)

        type_tracer.trace_call(
            "MockFacilitator.settle",
            result=settle_response
        )

        assert settle_response.success is True
        assert settle_response.transaction is not None

        logger.info("✓ Payment verified and settled successfully")

    def test_metadata_structure(self, type_tracer, mock_facilitator):
        """Test correct x402 metadata structure in responses."""
        middleware = x402PaymentMiddleware(facilitator=mock_facilitator)

        # Business logic that requires payment
        def paid_service(task: Task) -> Task:
            requirements = PaymentRequirements(
                scheme="exact",
                network="base-sepolia",
                asset="0x036CbD53842c5426634e7929541eC2318f3dCF7e",
                pay_to="0xMerchant",
                max_amount_required="5000000",
                description="Test product",
                resource="/product/test",
                mime_type="application/json",
                max_timeout_seconds=600
            )
            raise x402PaymentRequiredException(
                "Payment required",
                payment_requirements=[requirements]
            )

        # Create task
        message = Message(
            content=TextContent(text="Buy product"),
            role=MessageRole.USER
        )
        task = Task(
            message=message.to_dict()
        )

        # Execute
        result = middleware.process_task(task, paid_service)

        # Verify metadata structure - status.message is a dict
        status_message_dict = result.status.message
        assert status_message_dict is not None

        metadata = status_message_dict.get('metadata', {})
        custom_fields = metadata.get('custom_fields', metadata)

        # Check required fields per spec
        assert "x402.payment.status" in custom_fields
        assert custom_fields["x402.payment.status"] == "payment-required"

        assert "x402.payment.required" in custom_fields
        payment_required = custom_fields["x402.payment.required"]

        assert "x402Version" in payment_required
        assert payment_required["x402Version"] == 1

        assert "accepts" in payment_required
        assert isinstance(payment_required["accepts"], list)
        assert len(payment_required["accepts"]) > 0

        first_requirement = payment_required["accepts"][0]
        assert "scheme" in first_requirement
        assert "network" in first_requirement
        assert "maxAmountRequired" in first_requirement

        logger.info("✓ Metadata structure follows x402 spec")
