"""
Wallet implementations for x402 payment signing.

Based on reference implementation from a2a-x402/python/examples/adk-demo
"""

from abc import ABC, abstractmethod
import logging

import eth_account
from eth_account.account import Account

from x402_a2a.types import PaymentPayload, PaymentRequirements, x402PaymentRequiredResponse
from x402_a2a.core.wallet import process_payment_required

logger = logging.getLogger(__name__)


class Wallet(ABC):
    """
    Abstract base class for wallet implementations.

    This interface allows different wallet implementations (local, MPC,
    hardware wallets, custodial services) to be used interchangeably
    by client applications.
    """

    @abstractmethod
    def sign_payment(self, requirements: PaymentRequirements) -> PaymentPayload:
        """
        Sign a payment requirement and return the signed payload.

        Args:
            requirements: Payment requirements from merchant

        Returns:
            PaymentPayload with EIP-3009 signature

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError("Subclasses must implement sign_payment")


class MockLocalWallet(Wallet):
    """
    Mock wallet using a hardcoded private key.

    WARNING: FOR DEMONSTRATION/TESTING ONLY. DO NOT USE IN PRODUCTION.

    This wallet uses a well-known private key (private key = 1) which
    corresponds to address 0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf.

    For production:
    - Use hardware wallet (Ledger, Trezor)
    - Use MPC wallet service
    - Use secure key management system
    - Never hardcode private keys
    """

    # Well-known test private key (DO NOT USE IN PRODUCTION)
    _PRIVATE_KEY = "0x0000000000000000000000000000000000000000000000000000000000000001"

    def __init__(self):
        """Initialize the mock wallet."""
        self._account: Account = eth_account.Account.from_key(self._PRIVATE_KEY)
        logger.warning(
            f"MockLocalWallet initialized with address {self._account.address}. "
            "DO NOT USE IN PRODUCTION!"
        )

    @property
    def address(self) -> str:
        """Get the wallet's Ethereum address."""
        return self._account.address

    def sign_payment(self, requirements: PaymentRequirements) -> PaymentPayload:
        """
        Sign payment using EIP-3009 transfer authorization.

        Args:
            requirements: Single PaymentRequirements object

        Returns:
            PaymentPayload with signed EIP-3009 authorization

        Note:
            This method wraps a single PaymentRequirements into
            x402PaymentRequiredResponse format for the upstream
            process_payment_required function.
        """
        logger.info(f"Signing payment from {self.address}")
        logger.debug(f"Requirements: {requirements.model_dump_json(indent=2)}")

        # Wrap single requirement in x402PaymentRequiredResponse
        payment_required = x402PaymentRequiredResponse(
            x402_version=1,
            accepts=[requirements],
            error="Payment required"
        )

        # Use upstream x402_a2a wallet utility for EIP-3009 signing
        payload = process_payment_required(payment_required, self._account)

        logger.info("Payment signed successfully")
        return payload
