.PHONY: install run test lint format docker-up docker-down clean

# Installation
install:
	pip install -r requirements.txt
	cd frontend && npm install

# Development
run:
	python app.py

test:
	cd backend && python -m pytest tests/ -v --tb=short --cov=src

test-coverage:
	cd backend && python -m pytest tests/ -v --tb=short --cov=src --cov-report=html --cov-report=term

lint:
	cd backend && ruff check src/ tests/
	cd backend && mypy src/ --ignore-missing-imports
	cd frontend && npm run lint

format:
	cd backend && black src/ tests/ scripts/
	cd frontend && npx prettier --write "src/**/*.{ts,tsx,css}"
	ruff check src/ tests/ --fix

# Docker
docker-up:
	docker compose -f docker-compose.dev.yml up --build

docker-down:
	docker compose -f docker-compose.dev.yml down

docker-prod:
	docker compose up --build

# Pre-commit
precommit-install:
	pre-commit install

precommit-run:
	pre-commit run --all-files

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache 2>/dev/null || true
	rm -rf frontend/dist 2>/dev/null || true

# Help
help:
	@echo "Available commands:"
	@echo "  make install       - Install all dependencies"
	@echo "  make run           - Start the platform (backend + frontend)"
	@echo "  make test          - Run backend tests"
	@echo "  make test-coverage - Run tests with coverage report"
	@echo "  make lint          - Run linters (ruff, mypy, eslint)"
	@echo "  make format        - Format code (black, prettier)"
	@echo "  make docker-up     - Start dev Docker environment"
	@echo "  make docker-down   - Stop Docker environment"
	@echo "  make clean         - Clean cache and build artifacts"
