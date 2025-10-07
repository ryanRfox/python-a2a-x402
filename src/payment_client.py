"""
Payment-Aware Client for x402

This client wraps python-a2a's A2AClient and adds x402 payment handling.

Spec Compliance:
- Reads payment requirements from task.status.message.metadata
- Uses x402.payment.* dotted keys per spec
- Includes taskId for payment correlation
- Follows spec metadata structure
"""

import logging
from typing import Optional
import uuid

from python_a2a import (
    A2AClient,
    Task,
    TaskState,
    TaskStatus,
    Message,
    TextContent,
    MessageRole,
    Metadata
)

from x402_a2a.types import (
    PaymentRequirements,
    PaymentStatus,
)
from x402_a2a import X402_EXTENSION_URI

from wallet import MockLocalWallet

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _extract_custom_fields(message) -> dict:
    """
    Extract custom_fields from message metadata.

    Handles both dict and Message object formats, and extracts the
    custom_fields nested dict that contains x402 payment data.

    Args:
        message: Message dict or Message object

    Returns:
        dict: The custom_fields dict containing x402 metadata keys
    """
    if not message:
        return {}

    # Get metadata
    if isinstance(message, dict):
        metadata = message.get('metadata', {})
    else:
        metadata = getattr(message, 'metadata', {}) or {}

    # Extract custom_fields if present
    if isinstance(metadata, dict) and 'custom_fields' in metadata:
        return metadata['custom_fields']
    elif hasattr(metadata, 'custom_fields'):
        return metadata.custom_fields
    elif isinstance(metadata, dict):
        # Metadata might already be the custom_fields dict
        return metadata

    return {}


class PaymentAwareClient:
    """
    Client wrapper that adds x402 payment capabilities to python-a2a.

    This client:
    - Wraps python_a2a.A2AClient
    - Detects payment requirements from task.status.message.metadata
    - Prompts user for approval
    - Signs payments with wallet
    - Resubmits with signed payment and taskId correlation

    Usage:
        client = PaymentAwareClient("http://localhost:5001")
        response = client.ask("buy a laptop")
    """

    def __init__(
        self,
        endpoint_url: str,
        wallet: Optional[MockLocalWallet] = None
    ):
        """
        Initialize the payment-aware client.

        Per spec Section 7, client MUST request extension activation
        via X-A2A-Extensions header.

        Args:
            endpoint_url: URL of the merchant server
            wallet: Wallet for signing payments (creates MockLocalWallet if None)
        """
        # Add x402 extension activation header per spec Section 7
        headers = {
            "X-A2A-Extensions": X402_EXTENSION_URI
        }

        self.client = A2AClient(endpoint_url, headers=headers)
        self.wallet = wallet or MockLocalWallet()
        self.pending_payment: Optional[Task] = None

        logger.info(f"PaymentAwareClient initialized for {endpoint_url}")
        logger.info(f"x402 extension activation requested: {X402_EXTENSION_URI}")
        logger.info(f"Wallet address: {self.wallet.address}")

    def ask(self, message_text: str, auto_approve: bool = False) -> str:
        """
        Send a message and handle payment flow if needed.

        Args:
            message_text: Message to send to merchant
            auto_approve: If True, automatically approve payments (for testing)

        Returns:
            str: Response text from merchant
        """
        logger.info(f"Sending message: {message_text}")

        # Create a task and send it using the internal method
        task = self._create_task(message_text)
        result_task = self.client._send_task(task)

        # Check if payment is required
        if self._is_payment_required(result_task):
            logger.info("Payment required detected")
            return self._handle_payment_flow(result_task, auto_approve)

        # Return regular response
        return self._extract_response(result_task)

    def _create_task(self, message_text: str) -> Task:
        """Create a task with a message."""
        message = Message(
            content=TextContent(text=message_text),
            role=MessageRole.USER
        )

        task = Task(
            id=str(uuid.uuid4()),
            message=message.to_dict()
        )

        return task

    def _is_payment_required(self, task: Task) -> bool:
        """
        Check if task requires payment per spec.

        Looks for x402.payment.status in task.status.message.metadata

        Args:
            task: Task to check

        Returns:
            bool: True if payment is required
        """
        if task.status.state != TaskState.INPUT_REQUIRED:
            logger.debug(f"Task state is {task.status.state}, not INPUT_REQUIRED")
            return False

        if not hasattr(task.status, 'message') or not task.status.message:
            return False

        # Extract custom_fields from metadata
        metadata = _extract_custom_fields(task.status.message)

        status = metadata.get("x402.payment.status")

        is_required = status == PaymentStatus.PAYMENT_REQUIRED.value
        if is_required:
            logger.info("✓ Payment requirement detected")

        return is_required

    def _handle_payment_flow(
        self,
        task: Task,
        auto_approve: bool = False
    ) -> str:
        """
        Handle payment requirement and resubmit with signed payment.

        Args:
            task: Task with payment requirement
            auto_approve: Whether to auto-approve payment

        Returns:
            str: Response after payment completion
        """
        # Extract payment requirements from spec-compliant location
        if not task.status.message:
            raise ValueError("No message in task status")

        # Extract custom_fields from metadata
        metadata = _extract_custom_fields(task.status.message)

        if not metadata:
            raise ValueError("No metadata in task status message")

        payment_required = metadata.get("x402.payment.required")

        if not payment_required:
            raise ValueError("No payment requirements in metadata")

        accepts = payment_required.get("accepts", [])

        if not accepts:
            raise ValueError("No payment options provided")

        requirements_dict = accepts[0]

        # Convert to PaymentRequirements for display
        amount = requirements_dict.get("maxAmountRequired", "unknown")
        description = requirements_dict.get("description", "Unknown item")
        extra = requirements_dict.get("extra", {})
        currency = extra.get("name", "TOKEN")

        # Display payment request
        print("\n" + "=" * 60)
        print("💳 PAYMENT REQUIRED")
        print("=" * 60)
        print(f"Item: {description}")
        print(f"Amount: {amount} {currency}")
        print(f"Network: {requirements_dict.get('network', 'unknown')}")
        print(f"Merchant: {requirements_dict.get('payTo', 'unknown')}")
        print("=" * 60)

        # Get user approval
        if not auto_approve:
            confirm = input("\nApprove payment? (yes/no): ")
            if confirm.lower() != "yes":
                return "❌ Payment cancelled by user"

        # Sign payment
        print("\n💰 Signing payment...")
        logger.info("Signing payment with wallet")

        # Convert dict to PaymentRequirements for wallet
        requirements_obj = PaymentRequirements(**requirements_dict)

        signed_payload = self.wallet.sign_payment(requirements_obj)
        logger.info("Payment signed successfully")

        # Create payment submission task with proper metadata per spec
        # CRITICAL: Include taskId for correlation per spec section 4.5
        payment_message = Message(
            content=TextContent(
                text="Payment authorization provided"
            ),
            role=MessageRole.USER,
            metadata=Metadata(
                custom_fields={
                    "x402.payment.status": (
                        PaymentStatus.PAYMENT_SUBMITTED.value
                    ),
                    "x402.payment.payload": (
                        signed_payload.model_dump(by_alias=True)
                    )
                }
            )
        )

        payment_task = Task(
            id=task.id,  # Use same task ID for correlation
            status=TaskStatus(
                state=TaskState.INPUT_REQUIRED,  # Keep as input-required
                message=payment_message.to_dict()  # Convert to dict
            )
        )

        # Resubmit task with payment
        print("📤 Submitting payment...")
        logger.info(f"Resubmitting task {task.id} with signed payment")

        result_task = self.client._send_task(payment_task)

        # Extract response
        response = self._extract_response(result_task)

        # Check if payment was completed
        if self._is_payment_completed(result_task):
            print("\n✅ Payment completed successfully!\n")
            logger.info("Payment flow completed")

            # Display receipt if available
            receipts = self._get_payment_receipts(result_task)
            if receipts:
                logger.info(f"Received {len(receipts)} payment receipt(s)")
                for i, receipt in enumerate(receipts, 1):
                    if receipt.get("success"):
                        print(
                            f"Receipt {i}: TX {receipt.get('transaction')}"
                        )
        else:
            print("\n⚠️  Payment verification issue\n")
            logger.warning("Payment may not have been verified")

        return response

    def _is_payment_completed(self, task: Task) -> bool:
        """
        Check if payment was completed successfully per spec.

        Looks for x402.payment.status in task.status.message.metadata
        """
        if not hasattr(task.status, 'message') or not task.status.message:
            return False

        # Extract custom_fields from metadata
        metadata = _extract_custom_fields(task.status.message)

        status = metadata.get("x402.payment.status")
        return status == PaymentStatus.PAYMENT_COMPLETED.value

    def _get_payment_receipts(self, task: Task) -> list:
        """
        Get payment receipts from task per spec.

        Returns x402.payment.receipts array from metadata
        """
        if not hasattr(task.status, 'message') or not task.status.message:
            return []

        # Extract custom_fields from metadata
        metadata = _extract_custom_fields(task.status.message)

        return metadata.get("x402.payment.receipts", [])

    def _extract_response(self, task: Task) -> str:
        """Extract text response from task artifacts."""
        if not task.artifacts:
            return "No response"

        text_parts = []
        for artifact in task.artifacts:
            for part in artifact.get("parts", []):
                if part.get("type") == "text":
                    text_parts.append(part.get("text", ""))

        return "\n".join(text_parts) if text_parts else "No response"

    def interactive_session(self):
        """Run an interactive session with the merchant."""
        print("\n" + "=" * 60)
        print("x402 PAYMENT CLIENT - Interactive Session")
        print("=" * 60)
        print(f"Connected to: {self.client.endpoint_url}")
        print(f"Wallet: {self.wallet.address}")
        print("\nCommands:")
        print("  - Type a message to send to the merchant")
        print("  - 'exit' or 'quit' to stop")
        print("\nExamples:")
        print("  - What's your status?")
        print("  - Buy a laptop")
        print("=" * 60 + "\n")

        while True:
            try:
                user_input = input("> ").strip()

                if user_input.lower() in ["exit", "quit", "q"]:
                    print("\nGoodbye!")
                    break

                if not user_input:
                    continue

                response = self.ask(user_input)
                print(f"\n{response}\n")

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}\n")
                logger.error(f"Error: {e}", exc_info=True)


def main():
    """Run the payment client."""
    import argparse

    parser = argparse.ArgumentParser(description="x402 Payment Client")
    parser.add_argument(
        "--server",
        type=str,
        default="http://localhost:5001",
        help="Merchant server URL"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run automated test mode"
    )
    args = parser.parse_args()

    # Create client
    client = PaymentAwareClient(args.server)

    if args.test:
        # Test mode - automated flow
        print("\n=== TEST MODE ===\n")

        print("1. Testing public info request...")
        response = client.ask("What's your status?")
        print(f"Response: {response}\n")

        print("2. Testing payment flow...")
        response = client.ask("Buy a laptop", auto_approve=True)
        print(f"Response: {response}\n")

        print("=== TEST COMPLETE ===\n")
    else:
        # Interactive mode
        client.interactive_session()


if __name__ == "__main__":
    main()
