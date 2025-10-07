"""
Merchant Server with x402 Payment Support

This server extends python-a2a's A2AServer and integrates x402 payment
capabilities using the middleware pattern.
"""

import hashlib
import logging

from python_a2a import A2AServer, AgentCard, AgentSkill, Task, TaskStatus, TaskState

from x402_a2a.types import (
    PaymentRequirements,
    x402PaymentRequiredException,
)
from x402_a2a import (
    get_extension_declaration,
    X402_EXTENSION_URI,
    check_extension_activation,
)

from x402_middleware import x402PaymentMiddleware
from facilitator import MockFacilitator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MerchantServer(A2AServer):
    """
    A merchant server that sells products and accepts x402 payments.

    This server demonstrates how to integrate x402 payment capabilities
    with python-a2a's A2AServer using the middleware pattern.

    Features:
    - Free public information endpoint
    - Premium products requiring payment
    - x402 payment protocol integration
    - Deterministic pricing based on product name

    Architecture:
    - Inherits from python_a2a.A2AServer
    - Uses x402PaymentMiddleware for payment handling
    - Business logic raises x402PaymentRequiredException
    - Middleware catches exception and manages payment flow
    """

    def __init__(
        self,
        wallet_address: str = "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        port: int = 5001
    ):
        """
        Initialize the merchant server.

        Args:
            wallet_address: Merchant's Ethereum address for receiving payments
            port: Port to run server on
        """
        self.wallet_address = wallet_address
        self.port = port

        # Create agent card with x402 extension
        agent_card = self._create_agent_card()

        # Initialize python-a2a server
        super().__init__(agent_card=agent_card)

        # Initialize payment middleware
        facilitator = MockFacilitator()
        self.payment_middleware = x402PaymentMiddleware(facilitator)

        logger.info(f"MerchantServer initialized on port {port}")
        logger.info(f"Merchant wallet: {wallet_address}")

    def _create_agent_card(self) -> AgentCard:
        """Create agent card with x402 extension declaration."""
        return AgentCard(
            name="x402 Merchant",
            description="A merchant that sells products using x402 payment protocol",
            url=f"http://localhost:{self.port}",
            version="1.0.0",
            skills=[
                AgentSkill(
                    name="Get Public Info",
                    description="Get free public information about the merchant",
                    examples=["What's your status?", "Tell me about your service"]
                ),
                AgentSkill(
                    name="Buy Product",
                    description="Purchase a product with x402 payment",
                    examples=[
                        "Buy a laptop",
                        "I want to purchase a book",
                        "Sell me a phone"
                    ]
                )
            ],
            capabilities={
                "streaming": False,
                "extensions": [
                    get_extension_declaration(
                        description=(
                            "Supports x402 payment protocol "
                            "for product purchases"
                        ),
                        required=True
                    )
                ]
            }
        )

    def setup_routes(self, app):
        """
        Override setup_routes to add x402 extension activation header.

        Per spec Section 7, server MUST echo the extension URI in response
        header to confirm activation.
        """
        # Call parent setup_routes first
        super().setup_routes(app)

        # Add after_request handler to echo x402 extension header
        @app.after_request
        def add_x402_header(response):
            """Echo x402 extension URI in response header per spec Section 7."""
            from flask import request

            # Check if client requested x402 extension activation
            if check_extension_activation(request.headers):
                logger.debug("x402 extension activation detected, echoing header")
                response.headers["X-A2A-Extensions"] = X402_EXTENSION_URI

            return response

    def handle_task(self, task: Task) -> Task:
        """
        Handle incoming tasks with payment middleware.

        This method integrates x402 payment handling into python-a2a's
        task processing flow using the middleware pattern.

        Args:
            task: Incoming A2A task

        Returns:
            Task with results or payment requirements
        """
        logger.info(f"Handling task {task.id}")

        # Use middleware to process task with business logic
        return self.payment_middleware.process_task(task, self._execute_business_logic)

    def _execute_business_logic(self, task: Task) -> Task:
        """
        Execute merchant business logic.

        This method contains the actual business logic for the merchant.
        It processes requests and may raise x402PaymentRequiredException
        for premium content.

        Args:
            task: The task to process

        Returns:
            Task with results

        Raises:
            x402PaymentRequiredException: When payment is required
        """
        # Extract message text
        message_text = self._extract_message_text(task)
        logger.info(f"Processing message: {message_text}")

        # Check if this is a buy request
        if self._is_buy_request(message_text):
            return self._handle_buy_request(task, message_text)

        # Handle free information request
        return self._handle_public_info(task)

    def _is_buy_request(self, message: str) -> bool:
        """Check if message is a purchase request."""
        buy_keywords = ["buy", "purchase", "sell me", "get me", "want", "order"]
        message_lower = message.lower()
        return any(keyword in message_lower for keyword in buy_keywords)

    def _extract_message_text(self, task: Task) -> str:
        """Extract text from task message."""
        if not task.message:
            return ""

        content = task.message.get("content", {})

        # Handle different content formats
        if isinstance(content, dict):
            return content.get("text", "")
        elif isinstance(content, str):
            return content
        else:
            return ""

    def _extract_product_name(self, message: str) -> str:
        """Extract product name from buy request."""
        # Simple extraction: remove buy keywords and clean up
        message_lower = message.lower()

        for keyword in ["buy", "purchase", "sell me", "get me", "i want", "order"]:
            message_lower = message_lower.replace(keyword, "")

        # Remove articles
        for article in ["a ", "an ", "the "]:
            message_lower = message_lower.replace(article, "")

        product = message_lower.strip()
        return product if product else "item"

    def _calculate_price(self, product_name: str) -> int:
        """
        Calculate deterministic price for a product.

        Uses SHA256 hash of product name to generate consistent price.
        """
        price_hash = hashlib.sha256(product_name.lower().encode()).hexdigest()
        price = (int(price_hash, 16) % 99900001) + 100000
        return price

    def _handle_public_info(self, task: Task) -> Task:
        """Handle free public information request."""
        response_text = """
📊 Merchant Information

Welcome to the x402 Merchant Demo!

- Status: Online
- Payment Protocol: x402 (EIP-3009)
- Supported Network: base-sepolia
- Accepted Token: USDC

Try asking to buy something to see the payment flow in action!
Example: "Buy a laptop"
"""

        task.artifacts = [{
            "parts": [{"type": "text", "text": response_text.strip()}]
        }]
        task.status = TaskStatus(state=TaskState.COMPLETED)

        logger.info("Returned public info")
        return task

    def _handle_buy_request(self, task: Task, message: str) -> Task:
        """
        Handle product purchase request.

        This will raise x402PaymentRequiredException which will be
        caught by the middleware.

        Args:
            task: The task
            message: The buy request message

        Raises:
            x402PaymentRequiredException: Always raises to request payment
        """
        product_name = self._extract_product_name(message)
        price = self._calculate_price(product_name)

        logger.info(f"Product: {product_name}, Price: {price} USDC")

        # Create payment requirements with outputSchema per spec Section 5.2
        requirements = PaymentRequirements(
            scheme="exact",
            network="base-sepolia",
            asset="0x036CbD53842c5426634e7929541eC2318f3dCF7e",  # USDC on Base Sepolia
            pay_to=self.wallet_address,
            max_amount_required=str(price),
            description=f"Payment for: {product_name}",
            resource=f"https://merchant.example.com/products/{product_name}",
            mime_type="application/json",
            max_timeout_seconds=1200,
            output_schema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "string"},
                    "product": {"type": "string"},
                    "price": {"type": "number"},
                    "confirmation": {"type": "string"}
                },
                "required": ["order_id", "product", "confirmation"]
            },
            extra={
                "version": "1.0",  # Required for EIP-3009 signing
                "name": "USDC",
                "decimals": 6,
                "product": {
                    "name": product_name,
                    "sku": f"{product_name}_sku",
                    "price": price,
                }
            }
        )

        # Raise exception - middleware will catch and handle
        raise x402PaymentRequiredException(
            f"Payment required for {product_name}",
            payment_requirements=requirements
        )


def main():
    """Run the merchant server."""
    import argparse

    parser = argparse.ArgumentParser(description="x402 Merchant Server")
    parser.add_argument("--port", type=int, default=5001, help="Port to run on")
    parser.add_argument(
        "--wallet",
        type=str,
        default="0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B",
        help="Merchant wallet address"
    )
    args = parser.parse_args()

    # Create merchant server
    server = MerchantServer(wallet_address=args.wallet, port=args.port)

    # Run server
    from python_a2a import run_server

    print("\n" + "=" * 60)
    print("x402 MERCHANT SERVER")
    print("=" * 60)
    print(f"URL: http://localhost:{args.port}")
    print(f"Merchant Wallet: {args.wallet}")
    print(f"Agent: {server.agent_card.name}")
    print(f"Skills: {len(server.agent_card.skills)}")
    for skill in server.agent_card.skills:
        print(f"  - {skill.name}: {skill.description}")
    print("\nPress Ctrl+C to stop")
    print("=" * 60 + "\n")

    try:
        run_server(server, host="0.0.0.0", port=args.port)
    except KeyboardInterrupt:
        print("\n\nServer stopped")


if __name__ == "__main__":
    main()
