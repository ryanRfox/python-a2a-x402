# Contributing to python-a2a-x402

Thank you for your interest in contributing! This document provides guidelines for development, testing, and submitting contributions.

## Table of Contents

- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [Development Workflow](#development-workflow)
- [Testing](#testing)
- [Code Style](#code-style)
- [Documentation](#documentation)
- [Submitting Changes](#submitting-changes)

## Development Setup

### Prerequisites

- Python 3.12 or higher
- Git
- Virtual environment tool (venv)

### Initial Setup

1. **Clone the repository**
```bash
git clone https://github.com/ryanRfox/python-a2a-x402.git
cd python-a2a-x402
```

2. **Create and activate virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install all dependencies**
```bash
pip install -r requirements.txt
```

This will install all dependencies including `x402-a2a` directly from GitHub (it's not on PyPI). The requirements.txt uses PEP 440 direct references to automatically handle this.

### Verify Installation

```bash
# Run all tests
python -m pytest tests/ -v

# Should see: 41/41 tests passing (38 unit + 3 integration)
```

## Project Structure

```
python-a2a-x402/
├── src/                        # Source code
│   ├── merchant_server.py      # MerchantServer extending A2AServer
│   ├── x402_middleware.py      # Payment middleware for python-a2a
│   ├── payment_client.py       # PaymentAwareClient wrapper
│   ├── wallet.py               # MockLocalWallet with EIP-3009 signing
│   └── facilitator.py          # MockFacilitator for testing
├── tests/                      # Test suite (41/41 passing)
│   ├── README.md               # Testing documentation (pytest best practice)
│   ├── conftest.py             # Global fixtures and TypeTracer
│   ├── fixtures/               # Reusable test fixtures
│   │   ├── client_fixtures.py  # Wallet and client fixtures
│   │   └── server_fixtures.py  # Server and facilitator fixtures (port 5555)
│   ├── unit/                   # Unit tests (38/38 passing)
│   │   ├── test_wallet.py      # Wallet signing tests
│   │   ├── test_facilitator.py # Facilitator tests
│   │   ├── test_merchant_server.py # Merchant server tests
│   │   ├── test_x402_middleware.py # Middleware tests
│   │   ├── test_payment_client.py  # Client tests
│   │   └── test_http_headers.py    # HTTP header activation tests
│   └── integration/            # Integration tests (3/3 passing)
│       └── test_payment_flow.py    # End-to-end payment flow over HTTP
├── _PLANNING_/                 # Planning and design documents
│   ├── ARCHITECTURE_DECISION.md   # Why we use upstream x402-a2a
│   ├── ARCHITECTURE_ANALYSIS.md   # Initial architecture analysis
│   ├── DESIGN_PROPOSAL.md         # Original design proposal
│   ├── SPEC_COMPLIANCE_REPORT.md  # Spec compliance tracking
│   └── FUTURE_WORK.md             # Future enhancements
├── ARCHITECTURE.md             # Technical architecture documentation
├── README.md                   # Project overview and quick start
├── CONTRIBUTING.md             # This file
├── pytest.ini                  # Pytest configuration
└── requirements.txt            # Python dependencies
```

### Key Architecture Decisions

See [_PLANNING_/ARCHITECTURE_DECISION.md](_PLANNING_/ARCHITECTURE_DECISION.md) for the decision to use upstream `x402-a2a` package for types/constants while maintaining our own python-a2a-specific middleware implementation.

**What we use from upstream x402-a2a:**
- ✅ Types (Pydantic models): `PaymentRequirements`, `PaymentPayload`, etc.
- ✅ Exceptions: `x402PaymentRequiredException`
- ✅ Constants: `X402_EXTENSION_URI`

**What we implement ourselves:**
- 🔧 `src/x402_middleware.py` - python-a2a specific middleware
- 🔧 `src/payment_client.py` - Client using python-a2a types
- 🔧 `src/merchant_server.py` - Server extending `python_a2a.A2AServer`

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Your Changes

Follow these guidelines:
- Keep changes focused and atomic
- Write tests for new functionality
- Update documentation as needed
- Follow existing code style

### 3. Run Tests

```bash
# Run all unit tests
python -m pytest tests/unit/ -v

# Run specific test file
python -m pytest tests/unit/test_wallet.py -v

# Run with coverage (if pytest-cov installed)
python -m pytest tests/unit/ --cov=src --cov-report=html
```

### 4. Check Code Quality

```bash
# Format code (if using black)
black src/ tests/

# Lint code (if using flake8)
flake8 src/ tests/

# Type check (if using mypy)
mypy src/
```

### 5. Commit Your Changes

Follow conventional commit format:

```bash
git add .
git commit -m "feat: add new payment verification feature"

# Commit message format:
# <type>: <description>
#
# Types: feat, fix, docs, style, refactor, test, chore
```

### 6. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

## Testing

### Test Infrastructure

The project uses pytest with professional fixtures and comprehensive logging:

- **TypeTracer**: Custom utility for detailed function call tracing
- **Fixtures**: Reusable components (wallet, server, facilitator)
- **Scoped logging**: Trace execution flow through complex operations

See [tests/README.md](tests/README.md) for comprehensive testing documentation.

### Port Configuration

Tests use distinct ports to avoid conflicts:

| Environment | Port | Purpose |
|-------------|------|---------|
| **Production/Demo** | `5001` | Default merchant server |
| **Integration Tests** | `5555` | Test server (isolated) |
| **Unit Tests** | N/A | No server runs |

### Running Tests

```bash
# All tests (38 unit + 3 integration)
python -m pytest tests/ -v

# Only unit tests (38 passing)
python -m pytest tests/unit/ -v

# Only integration tests (3 passing)
python -m pytest tests/integration/ -v

# Specific test class
python -m pytest tests/unit/test_wallet.py::TestMockLocalWallet -v

# Specific test
python -m pytest tests/unit/test_wallet.py::TestMockLocalWallet::test_sign_payment -v

# With verbose logging
python -m pytest tests/ -v -s

# With detailed traceback
python -m pytest tests/ -v --tb=long

# Run integration tests while demo server runs on port 5001
python src/merchant_server.py  # Terminal 1
python -m pytest tests/integration/ -v  # Terminal 2 (no conflict!)
```

### Writing New Tests

1. **Create test file** in appropriate directory:
   - `tests/unit/` for unit tests
   - `tests/integration/` for integration tests

2. **Use fixtures** from `tests/fixtures/`:
   - `mock_wallet` - MockLocalWallet instance
   - `mock_facilitator` - MockFacilitator for payments
   - `merchant_server` - MerchantServer instance (port 5555)
   - `running_server` - Server running in background thread
   - `payment_client` - PaymentAwareClient instance
   - `connected_client` - Client connected to running server
   - `type_tracer` - TypeTracer for detailed logging

3. **Follow naming conventions**:
   - Test files: `test_*.py`
   - Test classes: `Test*`
   - Test functions: `test_*`

4. **Example test**:
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

## Code Style

### Python Style Guide

- Follow PEP 8
- Use type hints where possible
- Write docstrings for all public functions/classes
- Keep functions focused and small (<50 lines)
- Use descriptive variable names

### Example Function

```python
def sign_payment(self, requirements: PaymentRequirements) -> PaymentPayload:
    """
    Sign payment using EIP-3009 transfer authorization.

    Args:
        requirements: Payment requirements from merchant

    Returns:
        PaymentPayload with signed EIP-3009 authorization

    Raises:
        ValueError: If requirements are invalid
    """
    logger.info(f"Signing payment from {self.address}")
    # Implementation...
```

### Import Organization

```python
# Standard library
import logging
from typing import Optional

# Third-party
from pydantic import BaseModel
from python_a2a import A2AServer

# Local - upstream dependencies
from x402_a2a.types import PaymentRequirements

# Local - our code
from wallet import MockLocalWallet
```

## Documentation

### Required Documentation

When adding new features, update:

1. **Docstrings** - All public functions and classes
2. **README.md** - If changing user-facing behavior
3. **ARCHITECTURE.md** - If changing architecture
4. **tests/README.md** - If adding new test patterns
5. **_PLANNING_/** - Design decisions and future work

### Documentation Style

- Use clear, concise language
- Include code examples where helpful
- Add diagrams for complex flows (mermaid preferred)
- Keep docs in sync with code

### Generating Documentation

```bash
# Generate API docs (if using sphinx)
cd docs
make html

# View documentation
open _build/html/index.html
```

## Submitting Changes

### Pull Request Guidelines

1. **Title**: Clear, descriptive title
   - Good: "Add EIP-3009 signature validation"
   - Bad: "Fix stuff"

2. **Description**: Include:
   - What changed and why
   - Link to related issues
   - Testing performed
   - Breaking changes (if any)

3. **Checklist**:
   - [ ] All tests pass (`pytest tests/` - should see 41/41)
   - [ ] New tests added for new features
   - [ ] Documentation updated
   - [ ] Code follows style guide
   - [ ] Commits are clean and descriptive

### Example PR Description

```markdown
## Summary
Adds signature validation to the payment verification flow using eth-account.

## Changes
- Added `validate_signature()` method to facilitator
- Updated `verify()` to check EIP-3009 signature validity
- Added unit tests for signature validation

## Testing
- All existing tests pass
- Added 3 new tests for signature validation
- Tested with valid and invalid signatures

## Breaking Changes
None

## Related Issues
Closes #42
```

### Code Review Process

1. Maintainers will review your PR
2. Address any feedback or requested changes
3. Once approved, PR will be merged
4. Delete your feature branch after merge

## Development Tips

### Debugging

```bash
# Run tests with pdb on failure
python -m pytest tests/unit/ --pdb

# Run with verbose logging
python -m pytest tests/unit/ -v -s --log-cli-level=DEBUG
```

### Common Issues

**Import errors**:
```python
# Ensure src is in path for tests
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
```

**Pydantic model assertions**:
```python
# Use attribute access, not dict subscripting
assert payment.payload.authorization.from_ == expected
# NOT: payment.payload.authorization["from"]
```

**Async tests**:
```python
# Use pytest.mark.asyncio
@pytest.mark.asyncio
async def test_async_function():
    result = await async_operation()
```

### Useful Commands

```bash
# Find all TODOs
grep -r "TODO" src/

# Check for unused imports
flake8 --select=F401 src/

# Format all Python files
black src/ tests/

# Run security check
bandit -r src/
```

## Getting Help

- **Documentation**: Start with [README.md](README.md) and [ARCHITECTURE.md](ARCHITECTURE.md)
- **Testing**: See [tests/README.md](tests/README.md)
- **Architecture Decisions**: Check [_PLANNING_/](_PLANNING_/)
- **Issues**: Create an issue on GitHub
- **Questions**: Open a discussion on GitHub

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help newcomers learn
- Assume positive intent

Thank you for contributing to python-a2a-x402! 🎉
