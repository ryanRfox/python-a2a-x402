"""Unit tests for PaymentAwareClient."""

import pytest
import logging
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from payment_client import PaymentAwareClient, _extract_custom_fields
from wallet import MockLocalWallet
from python_a2a import Task, TaskStatus, TaskState, Message, TextContent, MessageRole, Metadata

logger = logging.getLogger(__name__)


class TestPaymentAwareClient:
    """Test suite for PaymentAwareClient."""

    def test_init(self, type_tracer, mock_wallet):
        """Test PaymentAwareClient initialization."""
        type_tracer.trace_call(
            "PaymentAwareClient.__init__",
            kwargs={
                'endpoint_url': "http://localhost:5001",
                'wallet': mock_wallet
            }
        )

        client = PaymentAwareClient(
            endpoint_url="http://localhost:5001",
            wallet=mock_wallet
        )

        type_tracer.trace_call(
            "PaymentAwareClient.__init__",
            result=client
        )

        assert client.wallet == mock_wallet
        assert client.client is not None
        assert client.pending_payment is None
        logger.info("✓ PaymentAwareClient initialized successfully")

    def test_init_creates_wallet_if_not_provided(self, type_tracer):
        """Test wallet is created if not provided."""
        client = PaymentAwareClient(endpoint_url="http://localhost:5001")

        assert client.wallet is not None
        assert isinstance(client.wallet, MockLocalWallet)
        logger.info("✓ Default wallet created when not provided")

    def test_extract_custom_fields_from_dict(self, type_tracer):
        """Test extracting custom fields from dict metadata."""
        metadata = {
            'custom_fields': {
                'x402.payment.status': 'payment-required',
                'x402.payment.required': {}
            }
        }

        type_tracer.trace_call(
            "_extract_custom_fields",
            kwargs={'message': {'metadata': metadata}}
        )

        custom_fields = _extract_custom_fields({'metadata': metadata})

        type_tracer.trace_call(
            "_extract_custom_fields",
            result=custom_fields
        )

        assert 'x402.payment.status' in custom_fields
        assert custom_fields['x402.payment.status'] == 'payment-required'
        logger.info("✓ Custom fields extracted from dict metadata")

    def test_extract_custom_fields_from_metadata_object(self, type_tracer):
        """Test extracting custom fields from Metadata object."""
        custom_fields_data = {
            'x402.payment.status': 'payment-required',
            'x402.payment.required': {}
        }

        metadata = Metadata(custom_fields=custom_fields_data)

        message = Message(
            content=TextContent(text="Test"),
            role=MessageRole.AGENT,
            metadata=metadata
        )

        type_tracer.trace_call(
            "_extract_custom_fields",
            kwargs={'message': message}
        )

        custom_fields = _extract_custom_fields(message)

        type_tracer.trace_call(
            "_extract_custom_fields",
            result=custom_fields
        )

        assert 'x402.payment.status' in custom_fields
        logger.info("✓ Custom fields extracted from Metadata object")

    def test_is_payment_required_detection(self, type_tracer, mock_wallet):
        """Test detection of payment-required status."""
        client = PaymentAwareClient(
            endpoint_url="http://localhost:5001",
            wallet=mock_wallet
        )

        # Create task with payment required - status.message is a dict
        custom_fields = {
            'x402.payment.status': 'payment-required',
            'x402.payment.required': {
                'x402Version': 1,
                'accepts': [{
                    'scheme': 'exact',
                    'network': 'base-sepolia',
                    'maxAmountRequired': '5000000'
                }]
            }
        }

        # Create message as dict (how it appears in status.message)
        message_dict = {
            'content': {'text': 'Payment required', 'type': 'text'},
            'role': 'agent',
            'metadata': {'custom_fields': custom_fields}
        }

        task = Task(
            status=TaskStatus(
                state=TaskState.INPUT_REQUIRED,
                message=message_dict
            )
        )

        type_tracer.trace_call(
            "PaymentAwareClient._is_payment_required",
            kwargs={'task': task}
        )

        is_required = client._is_payment_required(task)

        type_tracer.trace_call(
            "PaymentAwareClient._is_payment_required",
            result=is_required
        )

        assert is_required is True
        logger.info("✓ Payment required status detected correctly")

    def test_is_payment_required_false_for_normal_response(self, type_tracer, mock_wallet):
        """Test payment not required for normal response."""
        client = PaymentAwareClient(
            endpoint_url="http://localhost:5001",
            wallet=mock_wallet
        )

        # Create normal task with COMPLETED state
        task = Task(
            status=TaskStatus(state=TaskState.COMPLETED),
            artifacts=[{
                "parts": [{"type": "text", "text": "Here's your info"}]
            }]
        )

        is_required = client._is_payment_required(task)

        assert is_required is False
        logger.info("✓ Normal response not flagged as payment required")

    def test_create_task(self, type_tracer, mock_wallet):
        """Test task creation from message text."""
        client = PaymentAwareClient(
            endpoint_url="http://localhost:5001",
            wallet=mock_wallet
        )

        type_tracer.trace_call(
            "PaymentAwareClient._create_task",
            kwargs={'message_text': "Buy a laptop"}
        )

        task = client._create_task("Buy a laptop")

        type_tracer.trace_call(
            "PaymentAwareClient._create_task",
            result=task
        )

        # Task.message is a dict
        assert task.message is not None
        assert task.message['content']['text'] == "Buy a laptop"
        assert task.message['role'] == 'user'
        logger.info("✓ Task created from message text")

    def test_extract_response(self, type_tracer, mock_wallet):
        """Test extracting text response from task."""
        client = PaymentAwareClient(
            endpoint_url="http://localhost:5001",
            wallet=mock_wallet
        )

        task = Task(
            status=TaskStatus(state=TaskState.COMPLETED),
            artifacts=[{
                "parts": [{"type": "text", "text": "Here's your response"}]
            }]
        )

        type_tracer.trace_call(
            "PaymentAwareClient._extract_response",
            kwargs={'task': task}
        )

        response_text = client._extract_response(task)

        type_tracer.trace_call(
            "PaymentAwareClient._extract_response",
            result=response_text
        )

        assert response_text == "Here's your response"
        logger.info("✓ Response text extracted from task")

    def test_extract_response_no_artifacts(self, type_tracer, mock_wallet):
        """Test extracting response when no artifacts."""
        client = PaymentAwareClient(
            endpoint_url="http://localhost:5001",
            wallet=mock_wallet
        )

        task = Task(
            status=TaskStatus(state=TaskState.COMPLETED),
            artifacts=[]
        )

        response_text = client._extract_response(task)

        assert response_text == "No response"
        logger.info("✓ 'No response' returned when no artifacts")

    def test_payment_flow_detection(self, type_tracer, mock_wallet):
        """Test complete payment flow detection."""
        client = PaymentAwareClient(
            endpoint_url="http://localhost:5001",
            wallet=mock_wallet
        )

        # Use create_payment_requirements to get proper structure
        from x402_a2a import create_payment_requirements
        requirements = create_payment_requirements(
            price="$5.00",
            pay_to_address="0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
            resource="/product/test",
            network="base-sepolia",
            description="Test product"
        )

        # Convert to dict for metadata
        requirements_dict = requirements.model_dump(by_alias=True)

        # Simulate payment required response
        custom_fields = {
            'x402.payment.status': 'payment-required',
            'x402.payment.required': {
                'x402Version': 1,
                'accepts': [requirements_dict]
            }
        }

        message_dict = {
            'content': {'text': 'Payment required for laptop', 'type': 'text'},
            'role': 'agent',
            'metadata': {'custom_fields': custom_fields}
        }

        task = Task(
            id="test-task-123",
            status=TaskStatus(
                state=TaskState.INPUT_REQUIRED,
                message=message_dict
            )
        )

        # Test payment detection
        assert client._is_payment_required(task) is True

        # Test wallet can sign payment requirements
        signed_payload = mock_wallet.sign_payment(requirements)
        assert signed_payload is not None
        assert signed_payload.scheme == 'exact'
        assert signed_payload.network == 'base-sepolia'

        logger.info("✓ Complete payment flow detection verified")
