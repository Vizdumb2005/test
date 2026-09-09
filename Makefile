.PHONY: help install test lint format run ingest evaluate benchmark clean docker-build docker-up docker-down

help:
	@echo "Enterprise Hybrid RAG - Available commands"
	@echo "  make install       - Install dependencies"
	@echo "  make test          - Run tests"
	@echo "  make lint          - Run linting"
	@echo "  make format        - Format code"
	@echo "  make run           - Run API server"
	@echo "  make ingest        - Ingest demo data"
	@echo "  make evaluate      - Run evaluation"
	@echo "  make benchmark     - Run benchmark"
	@echo "  make docker-build  - Build Docker image"
	@echo "  make docker-up     - Start with Docker Compose"
	@echo "  make docker-down   - Stop Docker Compose"
	@echo "  make clean         - Clean generated files"

install:
	pip install --upgrade pip
	pip install -e ".[dev]"

test:
	pytest tests/ -v --tb=short

test-coverage:
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

lint:
	ruff check src/ tests/ scripts/

format:
	black src/ tests/ scripts/

run:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

ingest:
	python -m scripts.ingest ./data/raw

evaluate:
	python -m scripts.evaluate

benchmark:
	python -m scripts.benchmark

docker-build:
	docker compose build

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	rm -rf .coverage
