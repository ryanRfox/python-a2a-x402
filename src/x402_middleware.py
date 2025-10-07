"""
x402 Payment Middleware for python-a2a

This module provides middleware that adds x402 payment capabilities to
python-a2a servers. It follows the adapter pattern to integrate x402
payment flows with python-a2a's Task-based architecture.

Spec Compliance:
- Uses x402.payment.* dotted keys in task.status.message.metadata
- Payment status values in kebab-case per spec
- Includes x402Version field in responses
- Maintains receipt array with full payment history
- Follows spec metadata structure
"""

import logging
from typing import Dict, List, Optional

from python_a2a import (
    Task,
    TaskStatus,
    TaskState,
    Message,
    TextContent,
    MessageRole,
    Metadata
)

from x402_a2a.types import (
    PaymentRequirements,
    PaymentPayload,
    x402PaymentRequiredException,
    PaymentStatus,
    SettleResponse,
    x402ErrorCode,
)

logger = logging.getLogger(__name__)


def _get_metadata_dict(message) -> dict:
    """
    Extract metadata as dict from Message object.

    Handles both dict and Message object formats.
    """
    if not message:
        return {}

    if isinstance(message, dict):
        metadata = message.get('metadata', {})
        if isinstance(metadata, dict):
            # Check if it's a Metadata dict format
            return metadata.get('custom_fields', metadata)
        return {}

    # It's a Message object
    if not hasattr(message, 'metadata') or not message.metadata:
        return {}

    # Check if metadata is a Metadata object
    if hasattr(message.metadata, 'custom_fields'):
        return message.metadata.custom_fields
    elif isinstance(message.metadata, dict):
        return message.metadata

    return {}


class x402PaymentMiddleware:
    """
    Middleware that adds x402 payment handling to python-a2a servers.

    This class adapts the x402ServerExecutor pattern to work with python-a2a's
    A2AServer.handle_task() method. It provides:
    - Payment requirement exception handling
    - Payment verification
    - Payment settlement
    - State management per x402 spec

    Usage:
        middleware = x402PaymentMiddleware(facilitator=MockFacilitator())

        # In your server's handle_task:
        def handle_task(self, task):
            return middleware.process_task(task, business_logic_fn)
    """

    def __init__(self, facilitator):
        """
        Initialize the payment middleware.

        Args:
            facilitator: Payment facilitator for verify/settle operations.
                        Must implement verify(payload, requirements) and
                        settle(payload, requirements) methods.
        """
        self.facilitator = facilitator
        # Store list of payment requirements per task for correlation
        self.payment_store: Dict[str, List[PaymentRequirements]] = {}
        logger.info("x402PaymentMiddleware initialized")

    def process_task(self, task: Task, business_logic_fn) -> Task:
        """
        Process a task with payment middleware.

        This is the main entry point for integrating x402 payments into
        python-a2a's task handling flow.

        Args:
            task: The A2A Task to process
            business_logic_fn: Callable that executes business logic.
                             Should accept (task) and return Task.
                             May raise x402PaymentRequiredException.

        Returns:
            Task: Updated task with payment status or business logic result

        Flow:
            1. Check if task contains payment submission
            2. If payment: verify → execute logic → settle
            3. If no payment: execute logic
            4. If logic raises payment exception: handle and return payment
               required
        """
        try:
            # Check if this is a payment submission
            payment_status = self._get_payment_status(task)

            if payment_status == PaymentStatus.PAYMENT_SUBMITTED:
                logger.info(f"Task {task.id}: Processing payment submission")
                return self._handle_payment_submission(task, business_logic_fn)

            # Normal request - execute business logic
            try:
                logger.info(f"Task {task.id}: Executing business logic")
                return business_logic_fn(task)
            except x402PaymentRequiredException as e:
                logger.info(f"Task {task.id}: Payment required - {str(e)}")
                return self._handle_payment_required(task, e)
        except Exception as e:
            logger.error(
                f"Task {task.id}: Unexpected error in middleware - {e}",
                exc_info=True
            )
            task.status = TaskStatus(state=TaskState.FAILED)
            return task

    def _get_payment_status(self, task: Task) -> Optional[PaymentStatus]:
        """
        Extract payment status from task metadata per spec.

        Looks for x402.payment.status in task.status.message.metadata
        """
        if not task.status or not hasattr(task.status, 'message'):
            return None

        metadata = _get_metadata_dict(task.status.message)
        status_str = metadata.get("x402.payment.status")

        if not status_str:
            return None

        try:
            return PaymentStatus(status_str)
        except ValueError:
            return None

    def _handle_payment_required(
        self,
        task: Task,
        exception: x402PaymentRequiredException
    ) -> Task:
        """
        Handle x402PaymentRequiredException per spec.

        Creates payment required response with:
        - x402.payment.status: "payment-required"
        - x402.payment.required: { x402Version: 1, accepts: [...] }

        Args:
            task: Original task
            exception: The payment exception raised by business logic

        Returns:
            Task with INPUT_REQUIRED state and x402 payment requirements
        """
        # Store all requirements for verification later (spec requirement)
        self.payment_store[task.id] = exception.payment_requirements

        # Update task status to input-required per spec
        task.status = TaskStatus(state=TaskState.INPUT_REQUIRED)

        # Convert all payment requirements to dict format
        accepts = [
            req.model_dump(by_alias=True)
            for req in exception.payment_requirements
        ]

        # Ensure task has a status message for metadata (spec requirement)
        # Must convert to dict for proper serialization
        message = Message(
            content=TextContent(text=str(exception)),
            role=MessageRole.AGENT,
            metadata=Metadata(
                custom_fields={
                    "x402.payment.status": (
                        PaymentStatus.PAYMENT_REQUIRED.value
                    ),
                    "x402.payment.required": {
                        "x402Version": 1,  # Spec requirement
                        "accepts": accepts
                    }
                }
            )
        )
        task.status.message = message.to_dict()

        logger.info(
            f"Task {task.id}: Set to INPUT_REQUIRED with "
            f"{len(accepts)} payment options"
        )
        return task

    def _handle_payment_submission(
        self,
        task: Task,
        business_logic_fn
    ) -> Task:
        """
        Handle payment submission by verifying, executing logic, and settling.

        Args:
            task: Task with payment payload
            business_logic_fn: Business logic to execute after verification

        Returns:
            Task with business logic results and payment completion status
        """
        # Extract payment payload
        payload = self._get_payment_payload(task)
        if not payload:
            logger.error(f"Task {task.id}: No payment payload found")
            return self._fail_payment(
                task,
                x402ErrorCode.INVALID_SIGNATURE,
                "Missing payment data"
            )

        # Get stored requirements
        requirements_list = self.payment_store.get(task.id)
        if not requirements_list:
            logger.error(f"Task {task.id}: No stored payment requirements")
            return self._fail_payment(
                task,
                x402ErrorCode.INVALID_SIGNATURE,
                "Missing payment requirements"
            )

        # Find matching requirement from the list
        requirements = self._find_matching_requirement(
            requirements_list,
            payload
        )
        if not requirements:
            logger.error(f"Task {task.id}: No matching payment requirement")
            return self._fail_payment(
                task,
                x402ErrorCode.INVALID_SIGNATURE,
                "Payment does not match any accepted option"
            )

        # Validate payment expiry per spec Section 5.2
        if not self._validate_payment_expiry(requirements):
            logger.warning(f"Task {task.id}: Payment expired")
            return self._fail_payment(
                task,
                x402ErrorCode.EXPIRED_PAYMENT,
                "Payment authorization expired"
            )

        # Verify payment
        logger.info(f"Task {task.id}: Verifying payment with facilitator")
        try:
            verify_response = self.facilitator.verify(payload, requirements)
        except Exception as e:
            logger.error(f"Task {task.id}: Verification failed - {e}")
            return self._fail_payment(
                task,
                x402ErrorCode.INVALID_SIGNATURE,
                f"Verification failed: {e}"
            )

        if not verify_response.is_valid:
            logger.warning(f"Task {task.id}: Payment verification failed")
            return self._fail_payment(
                task,
                x402ErrorCode.INVALID_SIGNATURE,
                verify_response.invalid_reason or "Invalid payment"
            )

        logger.info(f"Task {task.id}: Payment verified successfully")

        # Update task with verified status
        self._record_payment_verified(task)

        # Payment verified - preserve message with metadata
        result_task = task
        # CRITICAL: Preserve the message with payment metadata
        result_task.status = TaskStatus(
            state=TaskState.COMPLETED,
            message=task.status.message  # Preserve payment metadata
        )

        # Add success artifact
        product_info = (
            requirements.extra.get("product", {})
            if requirements.extra else {}
        )
        product_name = product_info.get("name", "item")

        confirmation = (
            f"✅ Payment verified and order confirmed!\n\n"
            f"You have successfully purchased: {product_name}\n\n"
            f"Thank you for your business!"
        )
        result_task.artifacts = [{
            "parts": [{"type": "text", "text": confirmation}]
        }]

        # Settle payment
        logger.info(f"Task {task.id}: Settling payment")
        try:
            settle_response = self.facilitator.settle(payload, requirements)
        except Exception as e:
            logger.error(f"Task {task.id}: Settlement failed - {e}")
            settle_response = SettleResponse(
                success=False,
                network=requirements.network,
                errorReason=f"Settlement failed: {e}"
            )

        # Record settlement result with receipt array
        if settle_response.success:
            self._record_payment_success(task, settle_response)
        else:
            self._record_payment_failure(
                task,
                x402ErrorCode.SETTLEMENT_FAILED,
                settle_response
            )

        logger.info(f"Task {task.id}: Payment flow completed")

        # Clean up stored requirements
        if task.id in self.payment_store:
            del self.payment_store[task.id]

        return result_task

    def _find_matching_requirement(
        self,
        requirements_list: List[PaymentRequirements],
        payload: PaymentPayload
    ) -> Optional[PaymentRequirements]:
        """
        Find matching payment requirement from stored list.

        Matches based on scheme and network per spec.
        """
        for req in requirements_list:
            if req.scheme == payload.scheme and req.network == payload.network:
                return req
        return None

    def _validate_payment_expiry(
        self,
        requirements: PaymentRequirements
    ) -> bool:
        """
        Validate payment hasn't expired per spec Section 5.2.

        Checks maxTimeoutSeconds if present to prevent replay attacks.

        Returns:
            bool: True if payment is still valid, False if expired
        """
        if not hasattr(requirements, 'maxTimeoutSeconds'):
            # No expiry set, always valid
            return True

        max_timeout = requirements.maxTimeoutSeconds
        if not max_timeout or max_timeout <= 0:
            # No expiry or invalid value, always valid
            return True

        # Store creation time with requirements for validation
        # For this demo, we accept all payments within reasonable time
        # Production should track requirement creation timestamp
        logger.info(
            f"Payment expiry validation: maxTimeoutSeconds={max_timeout}"
        )

        # TODO: Implement actual timestamp checking when we track
        # requirement creation time
        return True

    def _get_payment_payload(self, task: Task) -> Optional[PaymentPayload]:
        """
        Extract payment payload from task metadata per spec.

        Looks for x402.payment.payload in task.status.message.metadata
        """
        if not task.status or not hasattr(task.status, 'message'):
            return None

        metadata = _get_metadata_dict(task.status.message)
        payload_dict = metadata.get("x402.payment.payload")

        if not payload_dict:
            return None

        try:
            return PaymentPayload(**payload_dict)
        except Exception as e:
            logger.error(f"Failed to parse payment payload: {e}")
            return None

    def _record_payment_verified(self, task: Task) -> None:
        """Record payment verification in task metadata per spec."""
        if not hasattr(task.status, 'message') or not task.status.message:
            return

        # Get current metadata or create new
        current_metadata = _get_metadata_dict(task.status.message)
        current_metadata["x402.payment.status"] = (
            PaymentStatus.PAYMENT_VERIFIED.value
        )

        # Update message dict directly (message is already a dict)
        if isinstance(task.status.message, dict):
            if 'metadata' not in task.status.message:
                task.status.message['metadata'] = {}
            task.status.message['metadata']['custom_fields'] = current_metadata
        else:
            task.status.message.metadata = Metadata(
                custom_fields=current_metadata
            )

    def _record_payment_success(
        self,
        task: Task,
        settle_response: SettleResponse
    ) -> None:
        """
        Record successful payment with settlement response per spec.

        Appends to x402.payment.receipts array (spec requirement).
        """
        if not hasattr(task.status, 'message') or not task.status.message:
            return

        # Get current metadata
        metadata = _get_metadata_dict(task.status.message)

        # Update status
        metadata["x402.payment.status"] = (
            PaymentStatus.PAYMENT_COMPLETED.value
        )

        # Append to receipts array (spec requirement for complete history)
        if "x402.payment.receipts" not in metadata:
            metadata["x402.payment.receipts"] = []

        metadata["x402.payment.receipts"].append(
            settle_response.model_dump(by_alias=True)
        )

        # Clean up intermediate data per spec
        metadata.pop("x402.payment.payload", None)
        metadata.pop("x402.payment.required", None)

        # Update message dict directly (message is already a dict)
        if isinstance(task.status.message, dict):
            if 'metadata' not in task.status.message:
                task.status.message['metadata'] = {}
            task.status.message['metadata']['custom_fields'] = metadata
        else:
            task.status.message.metadata = Metadata(custom_fields=metadata)

    def _record_payment_failure(
        self,
        task: Task,
        error_code: x402ErrorCode,
        settle_response: SettleResponse
    ) -> None:
        """
        Record payment failure with error details per spec.

        Appends to x402.payment.receipts array even on failure.
        """
        if not hasattr(task.status, 'message') or not task.status.message:
            return

        # Get current metadata
        metadata = _get_metadata_dict(task.status.message)

        # Update status
        metadata["x402.payment.status"] = (
            PaymentStatus.PAYMENT_FAILED.value
        )

        # Record error code (use value for spec compliance)
        metadata["x402.payment.error"] = error_code.value

        # Append to receipts array (spec requirement for complete history)
        if "x402.payment.receipts" not in metadata:
            metadata["x402.payment.receipts"] = []

        metadata["x402.payment.receipts"].append(
            settle_response.model_dump(by_alias=True)
        )

        # Clean up intermediate data
        metadata.pop("x402.payment.payload", None)

        # Update message dict directly (message is already a dict)
        if isinstance(task.status.message, dict):
            if 'metadata' not in task.status.message:
                task.status.message['metadata'] = {}
            task.status.message['metadata']['custom_fields'] = metadata
        else:
            task.status.message.metadata = Metadata(custom_fields=metadata)

    def _fail_payment(
        self,
        task: Task,
        error_code: x402ErrorCode,
        error_reason: str
    ) -> Task:
        """Handle payment failure before settlement attempt."""
        task.status = TaskStatus(state=TaskState.FAILED)

        failure_response = SettleResponse(
            success=False,
            network="base",  # Default network
            errorReason=error_reason
        )

        self._record_payment_failure(task, error_code, failure_response)

        # Clean up stored requirements
        self.payment_store.pop(task.id, None)

        return task
