"""
pytest configuration and shared fixtures for the test suite.

This module provides:
- Logging configuration with detailed tracing
- Shared fixtures for server, client, facilitator
- Test utilities for type inspection and validation
"""

import logging
import sys
import json
from typing import Any, Dict
import pytest
from contextlib import contextmanager


# Configure logging for tests
def setup_test_logging():
    """Configure comprehensive test logging."""
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler with detailed format
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    # Detailed format showing module, function, and line number
    formatter = logging.Formatter(
        '%(asctime)s.%(msecs)03d | %(levelname)-8s | '
        '%(name)-30s | %(funcName)-25s:%(lineno)-4d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    return root_logger


@pytest.fixture(scope="session", autouse=True)
def configure_logging():
    """Auto-configure logging for all tests."""
    return setup_test_logging()


@pytest.fixture
def trace_logger():
    """Provide a logger for detailed test tracing."""
    logger = logging.getLogger("test.trace")
    return logger


class TypeTracer:
    """Utility for tracing function calls with type information."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def trace_call(
        self,
        func_name: str,
        args: tuple = (),
        kwargs: dict = None,
        result: Any = None,
        error: Exception = None
    ):
        """
        Trace a function call with full type information.

        Args:
            func_name: Name of the function being called
            args: Positional arguments
            kwargs: Keyword arguments
            result: Return value (if successful)
            error: Exception (if raised)
        """
        kwargs = kwargs or {}

        # Format input arguments
        input_info = {
            'args': [self._format_value(arg) for arg in args],
            'kwargs': {k: self._format_value(v) for k, v in kwargs.items()}
        }

        self.logger.info(f"CALL: {func_name}")
        self.logger.debug(f"  INPUT: {json.dumps(input_info, indent=2)}")

        if error:
            self.logger.error(f"  ERROR: {type(error).__name__}: {error}")
        elif result is not None:
            result_info = self._format_value(result)
            self.logger.debug(f"  RETURN: {json.dumps(result_info, indent=2)}")

    def _format_value(self, value: Any) -> Dict[str, Any]:
        """Format a value for logging with type information."""
        if value is None:
            return {'type': 'NoneType', 'value': None}

        value_type = type(value).__name__

        # Handle Pydantic models
        if hasattr(value, 'model_dump'):
            return {
                'type': value_type,
                'value': value.model_dump(mode='json'),
                'schema': value.__class__.__name__
            }

        # Handle dataclasses
        if hasattr(value, '__dataclass_fields__'):
            return {
                'type': value_type,
                'value': str(value),
                'fields': list(value.__dataclass_fields__.keys())
            }

        # Handle primitives
        if isinstance(value, (str, int, float, bool)):
            return {'type': value_type, 'value': value}

        # Handle dicts
        if isinstance(value, dict):
            return {
                'type': 'dict',
                'keys': list(value.keys()),
                'sample': {k: type(v).__name__ for k, v in list(value.items())[:3]}
            }

        # Handle lists
        if isinstance(value, (list, tuple)):
            return {
                'type': value_type,
                'length': len(value),
                'item_types': [type(item).__name__ for item in value[:3]]
            }

        # Fallback
        return {'type': value_type, 'repr': repr(value)[:100]}


@pytest.fixture
def type_tracer(trace_logger):
    """Provide a TypeTracer instance for tests."""
    return TypeTracer(trace_logger)


@contextmanager
def trace_scope(logger: logging.Logger, scope_name: str):
    """
    Context manager for tracing a scope of operations.

    Usage:
        with trace_scope(logger, "Payment Flow"):
            # operations here
    """
    logger.info(f"{'='*80}")
    logger.info(f"BEGIN: {scope_name}")
    logger.info(f"{'='*80}")
    try:
        yield
    finally:
        logger.info(f"{'='*80}")
        logger.info(f"END: {scope_name}")
        logger.info(f"{'='*80}")


@pytest.fixture
def trace_scope_fixture(trace_logger):
    """Provide trace_scope as a fixture."""
    def _trace_scope(scope_name: str):
        return trace_scope(trace_logger, scope_name)
    return _trace_scope


# Import fixtures from fixtures/ directory
pytest_plugins = [
    "tests.fixtures.client_fixtures",
    "tests.fixtures.server_fixtures",
]
