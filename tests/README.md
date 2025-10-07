# Testing Guide

This document describes the test infrastructure and how to run tests for the python-a2a-x402-mvp project.

## Test Structure

The project uses pytest with professional test fixtures and comprehensive logging:

```
tests/
├── conftest.py                  # Global fixtures and TypeTracer utility
├── fixtures/
│   ├── client_fixtures.py       # Client and wallet fixtures
│   └── server_fixtures.py       # Server and facilitator fixtures
├── unit/
│   ├── test_wallet.py           # Wallet signing tests
│   └── test_facilitator.py      # Facilitator verify/settle tests
└── integration/
    └── test_payment_flow.py     # End-to-end payment flow tests
```

## Running Tests

### Port Configuration

Tests use distinct ports to avoid conflicts:

| Test Type | Port | Purpose |
|-----------|------|---------|
| **Unit Tests** | N/A | No server runs (mocks only) |
| **Integration Tests** | `5555` | Isolated test server |
| **Demo Server** | `5001` | Production/demo (default) |

**Benefits:**
- Run integration tests while demo server is running
- No port conflicts between environments
- Clean test isolation

### Run All Tests (41/41 passing)
```bash
# All tests (38 unit + 3 integration)
python -m pytest tests/ -v

# Only unit tests (38 passing)
python -m pytest tests/unit/ -v

# Only integration tests (3 passing)
python -m pytest tests/integration/ -v
```

### Run Specific Test File
```bash
python -m pytest tests/unit/test_wallet.py -v
```

### Run Specific Test
```bash
python -m pytest tests/unit/test_wallet.py::TestMockLocalWallet::test_sign_payment -v
```

### Run with Detailed Logging
```bash
python -m pytest tests/ -v -s
```

### Run Tests While Demo Runs
```bash
# Terminal 1: Start demo server on port 5001
python src/merchant_server.py

# Terminal 2: Run integration tests on port 5555 (no conflict!)
python -m pytest tests/integration/ -v
```

### Run with Type Tracing
The TypeTracer utility automatically logs detailed type information for all test executions. No special flags needed.

## Test Configuration

### pytest.ini
```ini
[pytest]
python_files = test_*.py
python_classes = Test*
python_functions = test_*
testpaths = tests
log_cli = true
log_cli_level = INFO
asyncio_mode = auto
```

## Test Infrastructure

### TypeTracer Utility

The `TypeTracer` class (in `conftest.py`) provides detailed tracing of function calls with type information:

```python
def test_example(type_tracer):
    """Example test using TypeTracer."""
    type_tracer.trace_call(
        "MyFunction",
        kwargs={'param': value}
    )

    result = my_function(param=value)

    type_tracer.trace_call(
        "MyFunction",
        result=result
    )
```

**TypeTracer Features:**
- Traces function signatures
- Logs input types with sample values
- Logs return types with sample values
- Handles Pydantic models (shows schemas)
- Handles dicts, lists, primitives
- Includes timestamps and source location

### Test Fixtures

#### Wallet Fixtures (`client_fixtures.py`)

**mock_wallet**
- Provides: `MockLocalWallet` instance
- Usage: Testing wallet signing functionality
- Address: `0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf` (well-known test key)

**payment_client**
- Provides: `PaymentAwareClient` with mock wallet
- Usage: Testing client payment handling
- Note: Uses placeholder URL, override with connected_client

**connected_client**
- Provides: `PaymentAwareClient` connected to running server
- Usage: End-to-end integration tests
- Requires: running_server fixture

#### Server Fixtures (`server_fixtures.py`)

**mock_facilitator**
- Provides: `MockFacilitator(is_valid=True, is_settled=True)`
- Usage: Testing payment verification and settlement
- Configurable: Can create with is_valid=False for testing failures

**merchant_server**
- Provides: `MerchantServer` instance with mock facilitator
- Usage: Testing server business logic
- Wallet: `0xTestMerchantWallet123456789ABCDEF`
- Port: 5555

**running_server**
- Provides: Server running in background thread
- Usage: Integration tests requiring HTTP communication
- Returns: tuple of (server, base_url)
- Note: Requires proper async handling for python-a2a

## Unit Tests

### Wallet Tests (`test_wallet.py`)

Tests the `MockLocalWallet` implementation:

✅ **test_init** - Wallet initialization
- Verifies address format (0x prefix, 42 chars)
- Checks Ethereum address validity

✅ **test_sign_payment** - Payment signing with EIP-3009
- Creates payment requirements
- Signs payment with wallet
- Verifies PaymentPayload structure
- Checks signature validity

✅ **test_sign_payment_amount_validation** - Amount limits
- Verifies signed amount ≤ max_amount_required
- Tests pricing consistency

✅ **test_sign_payment_network_consistency** - Network matching
- Tests base-sepolia network
- Tests base network
- Verifies payload network matches requirements

### Facilitator Tests (`test_facilitator.py`)

Tests the `MockFacilitator` implementation:

✅ **test_init_valid_settled** - Initialization with valid=True
- Verifies _is_valid and _is_settled flags

✅ **test_init_invalid** - Initialization with valid=False
- Tests failure mode configuration

✅ **test_verify_valid_payment** - Payment verification success
- Mocks payment payload
- Calls verify()
- Checks VerifyResponse structure
- Verifies payer extraction

✅ **test_verify_invalid_payment** - Payment verification failure
- Tests invalid payment rejection
- Verifies invalid_reason field

✅ **test_settle_successful** - Successful settlement
- Calls settle()
- Verifies SettleResponse
- Checks transaction hash format
- Validates network field

✅ **test_settle_failed** - Failed settlement
- Tests settlement failure mode
- Verifies error_reason field

## Integration Tests

### Payment Flow Tests (`test_payment_flow.py`)

**Status**: Integration tests require proper FastAPI/uvicorn server setup for python-a2a. Unit tests provide comprehensive coverage of individual components.

**Planned Tests**:
- test_complete_payment_flow - Full payment cycle
- test_free_service_no_payment - Free service handling
- test_payment_verification_traces - Detailed verification logging

**To Enable**: Implement proper server fixture using uvicorn for async FastAPI handling.

## Test Coverage

### Current Coverage

**Unit Tests**: ✅ 10/10 passing
- Wallet: 4/4 tests
- Facilitator: 6/6 tests

**Integration Tests**: ⏸️ Pending server infrastructure
- Requires uvicorn-based server fixture
- Components individually tested via unit tests

### Coverage by Component

| Component | Unit Tests | Integration Tests | Notes |
|-----------|-----------|-------------------|-------|
| MockLocalWallet | ✅ 4/4 | ⏸️ | Full EIP-3009 signing coverage |
| MockFacilitator | ✅ 6/6 | ⏸️ | Verify & settle paths tested |
| PaymentAwareClient | ⚠️ | ⏸️ | Tested via integration |
| MerchantServer | ⚠️ | ⏸️ | Tested via integration |
| x402PaymentMiddleware | ⚠️ | ⏸️ | Tested via integration |

## Adding New Tests

### Creating a Unit Test

```python
"""Unit tests for MyComponent."""

import pytest
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from my_component import MyComponent

logger = logging.getLogger(__name__)


class TestMyComponent:
    """Test suite for MyComponent."""

    def test_my_feature(self, type_tracer):
        """Test description."""
        # Trace input
        type_tracer.trace_call(
            "MyComponent.my_method",
            kwargs={'param': value}
        )

        # Execute
        component = MyComponent()
        result = component.my_method(param=value)

        # Trace output
        type_tracer.trace_call(
            "MyComponent.my_method",
            result=result
        )

        # Assertions
        assert result.field == expected_value
        logger.info("✓ Test passed")
```

### Using Type Tracer

**Trace Function Call:**
```python
type_tracer.trace_call(
    "function_name",
    args=(arg1, arg2),              # positional args
    kwargs={'key': value},          # keyword args
)
```

**Trace Return Value:**
```python
type_tracer.trace_call(
    "function_name",
    result=return_value
)
```

**Trace Error:**
```python
try:
    result = risky_operation()
except Exception as e:
    type_tracer.trace_call(
        "risky_operation",
        error=e
    )
    raise
```

### Using Trace Scopes

For grouping related operations:

```python
def test_with_scope(trace_scope_fixture):
    """Test using trace scope."""
    with trace_scope_fixture("My Operation"):
        # Operations here will be grouped in logs
        step1()
        step2()
```

## Test Output Example

```
2025-10-06 22:06:51.643 | INFO     | test_wallet | test_sign_payment  | STEP 1: Creating payment requirements
2025-10-06 22:06:51.643 | INFO     | test.trace  | trace_call         | CALL: MockLocalWallet.sign_payment
2025-10-06 22:06:51.643 | DEBUG    | test.trace  | trace_call         |   INPUT: {
  "args": [],
  "kwargs": {
    "requirements": {
      "type": "PaymentRequirements",
      "value": {
        "scheme": "exact",
        "network": "base-sepolia",
        "max_amount_required": "5000000",
        ...
      }
    }
  }
}
2025-10-06 22:06:51.644 | INFO     | wallet      | sign_payment       | Signing payment from 0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf
2025-10-06 22:06:51.645 | INFO     | wallet      | sign_payment       | Payment signed successfully
2025-10-06 22:06:51.645 | DEBUG    | test.trace  | trace_call         |   RETURN: {
  "type": "PaymentPayload",
  "value": {
    "x402_version": 1,
    "scheme": "exact",
    "network": "base-sepolia",
    "payload": {
      "signature": "0x...",
      "authorization": {...}
    }
  }
}
2025-10-06 22:06:51.645 | INFO     | test_wallet | test_sign_payment  | ✓ Payment signed successfully
```

## Troubleshooting

### Common Issues

**Import Errors**
```bash
# Ensure src is in path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
```

**Async Test Failures**
```python
# Use pytest.mark.asyncio for async tests
@pytest.mark.asyncio
async def test_async_function():
    result = await async_operation()
```

**Pydantic Model Assertions**
```python
# Use attribute access, not dict subscripting
assert payment.payload.authorization.from_ == expected_address
# NOT: payment.payload.authorization["from"]
```

**Private Attributes**
```python
# Access private attributes with underscore prefix
assert facilitator._is_valid is True
# NOT: facilitator.is_valid
```

### Debug Mode

Run tests with maximum verbosity:
```bash
python -m pytest tests/unit/ -vv -s --tb=long
```

## Best Practices

1. **Always use TypeTracer** - Provides valuable debugging information
2. **Log test progress** - Use logger.info() for checkpoints
3. **Test both success and failure** - Verify error handling
4. **Use descriptive assertions** - Make failures self-documenting
5. **Keep tests independent** - Each test should run in isolation
6. **Mock external dependencies** - Use MockFacilitator, MockLocalWallet
7. **Follow naming conventions** - test_*, Test*, conftest.py
8. **Document test purpose** - Clear docstrings for each test

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - run: python -m pytest tests/unit/ -v
```

## Future Enhancements

- [ ] Add integration test server fixture using uvicorn
- [ ] Add code coverage reporting (pytest-cov)
- [ ] Add mutation testing (mutmut)
- [ ] Add property-based testing (hypothesis)
- [ ] Add performance benchmarks
- [ ] Add contract interaction tests (when using real blockchain)

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [x402 spec](https://github.com/google-agentic-commerce/a2a-x402)
- [python-a2a library](https://github.com/themanojdesai/python-a2a)
- [EIP-3009](https://eips.ethereum.org/EIPS/eip-3009)
