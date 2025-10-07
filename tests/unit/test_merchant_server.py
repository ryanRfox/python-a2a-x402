"""Unit tests for MerchantServer."""

import pytest
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from merchant_server import MerchantServer
from python_a2a import Task, TaskStatus, TaskState, Message, TextContent, MessageRole

logger = logging.getLogger(__name__)


class TestMerchantServer:
    """Test suite for MerchantServer."""

    def test_init(self, type_tracer):
        """Test MerchantServer initialization."""
        type_tracer.trace_call(
            "MerchantServer.__init__",
            kwargs={
                'wallet_address': "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
                'port': 5001
            }
        )

        server = MerchantServer(
            wallet_address="0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
            port=5001
        )

        type_tracer.trace_call(
            "MerchantServer.__init__",
            result=server
        )

        assert server.wallet_address == "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B"
        assert server.port == 5001
        assert server.payment_middleware is not None
        logger.info("✓ MerchantServer initialized successfully")

    def test_create_agent_card(self, type_tracer):
        """Test agent card creation with x402 extension."""
        server = MerchantServer(
            wallet_address="0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
            port=5001
        )

        # Access the agent card
        agent_card = server.agent_card

        type_tracer.trace_call(
            "MerchantServer._create_agent_card",
            result=agent_card
        )

        assert agent_card.name == "x402 Merchant"
        assert "x402 payment protocol" in agent_card.description.lower()
        assert len(agent_card.skills) >= 2  # At least public info and buy product
        assert agent_card.capabilities is not None

        # Check for x402 extension in capabilities
        extensions = agent_card.capabilities.get("extensions", [])
        assert len(extensions) > 0
        assert any("x402" in str(ext).lower() for ext in extensions)

        logger.info("✓ Agent card created with x402 extension")

    def test_handle_task_free_service(self, type_tracer, mock_facilitator):
        """Test handling free service request (no payment required)."""
        server = MerchantServer(
            wallet_address="0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
            port=5001
        )
        server.payment_middleware.facilitator = mock_facilitator

        # Create task for free service
        message = Message(
            content=TextContent(text="What's your status?"),
            role=MessageRole.USER
        )
        task = Task(
            message=message.to_dict()
        )

        type_tracer.trace_call(
            "MerchantServer.handle_task",
            kwargs={'task': task}
        )

        # Handle the task
        result_task = server.handle_task(task)

        type_tracer.trace_call(
            "MerchantServer.handle_task",
            result=result_task
        )

        # Should complete without payment
        assert result_task.status.state == TaskState.COMPLETED
        assert result_task.artifacts is not None
        assert len(result_task.artifacts) > 0
        # Extract text from artifacts
        text = result_task.artifacts[0]["parts"][0]["text"]
        assert "merchant" in text.lower()

        logger.info("✓ Free service handled without payment requirement")

    def test_handle_task_requires_payment(self, type_tracer, mock_facilitator):
        """Test handling request that requires payment."""
        server = MerchantServer(
            wallet_address="0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
            port=5001
        )
        server.payment_middleware.facilitator = mock_facilitator

        # Create task for paid service
        message = Message(
            content=TextContent(text="Buy a laptop"),
            role=MessageRole.USER
        )
        task = Task(
            message=message.to_dict()
        )

        type_tracer.trace_call(
            "MerchantServer.handle_task",
            kwargs={'task': task}
        )

        # Handle the task
        result_task = server.handle_task(task)

        type_tracer.trace_call(
            "MerchantServer.handle_task",
            result=result_task
        )

        # Should return payment requirement
        assert result_task.status.state == TaskState.INPUT_REQUIRED
        assert result_task.status.message is not None

        # Check for payment metadata - status.message is a dict
        status_message_dict = result_task.status.message
        metadata = status_message_dict.get('metadata', {})
        custom_fields = metadata.get('custom_fields', metadata)
        assert "x402.payment.status" in custom_fields
        assert custom_fields["x402.payment.status"] == "payment-required"
        assert "x402.payment.required" in custom_fields

        logger.info("✓ Payment requirement returned for paid service")

    def test_pricing_logic(self, type_tracer):
        """Test deterministic pricing based on product name."""
        server = MerchantServer(
            wallet_address="0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
            port=5001
        )

        # Test same product gives same price
        message1 = Message(
            content=TextContent(text="Buy a laptop"),
            role=MessageRole.USER
        )
        task1 = Task(
            message=message1.to_dict()
        )

        result1 = server.handle_task(task1)

        message2 = Message(
            content=TextContent(text="Purchase a laptop"),
            role=MessageRole.USER
        )
        task2 = Task(
            message=message2.to_dict()
        )

        result2 = server.handle_task(task2)

        # Extract payment requirements from both - status.message is a dict
        status_msg1 = result1.status.message
        status_msg2 = result2.status.message

        if status_msg1 and status_msg2:
            metadata1 = status_msg1.get('metadata', {})
            metadata2 = status_msg2.get('metadata', {})

            cf1 = metadata1.get('custom_fields', metadata1)
            cf2 = metadata2.get('custom_fields', metadata2)

            if "x402.payment.required" in cf1 and "x402.payment.required" in cf2:
                req1 = cf1["x402.payment.required"]
                req2 = cf2["x402.payment.required"]

                # Same product should have same price
                if "accepts" in req1 and "accepts" in req2:
                    price1 = req1["accepts"][0].get("maxAmountRequired")
                    price2 = req2["accepts"][0].get("maxAmountRequired")
                    assert price1 == price2
                    logger.info(f"✓ Deterministic pricing verified: {price1} USDC")
                    return

        logger.info("✓ Pricing logic test completed")
