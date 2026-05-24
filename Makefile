.PHONY: help up down restart logs test test-unit test-integration test-backtest \
        lint format migrate init-db train-regime run-sandbox merge-gate install

help:
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

# ── Infrastructure ────────────────────────────────────────────────────────────

up: ## Start all Docker services
	docker compose -f docker/docker-compose.yml up -d

down: ## Stop all Docker services
	docker compose -f docker/docker-compose.yml down

restart: ## Restart all Docker services
	docker compose -f docker/docker-compose.yml restart

logs: ## Tail logs for all services
	docker compose -f docker/docker-compose.yml logs -f

# ── Development ───────────────────────────────────────────────────────────────

install: ## Install all dependencies (including dev)
	pip install -e ".[dev,backtest]"

lint: ## Run ruff + mypy
	ruff check src tests
	mypy src

format: ## Auto-format with ruff
	ruff format src tests
	ruff check --fix src tests

# ── Database ──────────────────────────────────────────────────────────────────

migrate: ## Run Alembic migrations (upgrade head)
	alembic -c src/bot_scalp_x/database/migrations/alembic.ini upgrade head

init-db: ## Initialize DB schema + seed data
	python scripts/init_db.py

# ── Testing ───────────────────────────────────────────────────────────────────

test: ## Run all tests (unit + integration)
	pytest tests/unit tests/integration -v --tb=short

test-unit: ## Run unit tests only (fast, no I/O)
	pytest tests/unit -v -q

test-integration: ## Run integration tests (requires Docker services)
	pytest tests/integration -v --tb=short

test-backtest: ## Run backtest suite
	pytest tests/backtests -v --tb=short

# ── Bot Operations ────────────────────────────────────────────────────────────

train-regime: ## Train regime classifier model
	python scripts/train_regime_model.py

run-sandbox: ## Run Phase 7 sanity suite → sanity_report.json
	python scripts/run_sandbox.py

merge-gate: ## Run full merge gate (unit + integration + backtest + sandbox)
	python tests/merge_gate/run_gate.py
