.PHONY: help install install-dev test test-unit test-integration lint format clean run-merchant run-client

help:
	@echo "Available commands:"
	@echo "  make install       - Install production dependencies"
	@echo "  make install-dev   - Install development dependencies"
	@echo "  make test          - Run all tests"
	@echo "  make test-unit     - Run unit tests only"
	@echo "  make test-integration - Run integration tests"
	@echo "  make lint          - Run linting (flake8)"
	@echo "  make format        - Format code (black, isort)"
	@echo "  make clean         - Remove cache and build artifacts"
	@echo "  make run-merchant  - Run merchant server"
	@echo "  make run-client    - Run interactive client"

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install pytest flake8 black isort

test:
	pytest tests/unit/ -v

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

lint:
	flake8 src/ tests/

format:
	isort src/ tests/
	black src/ tests/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*~" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ .pytest_cache/

run-merchant:
	python src/merchant_server.py

run-client:
	python src/payment_client.py
