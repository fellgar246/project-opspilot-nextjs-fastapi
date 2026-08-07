SHELL := /bin/bash
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
COMPOSE := docker compose
PROFILE ?= minimal
UV := uv
PNPM := $(if $(wildcard node_modules/.bin/pnpm),./node_modules/.bin/pnpm,$(shell command -v pnpm 2>/dev/null || echo npx\ --yes\ pnpm@9))

.PHONY: bootstrap up down reset lint format typecheck test migrate compose-validate build security-scan smoke seed-users seed-services seed-perf sim-seed sim-reset sim-scenario ingest-runbooks eval eval-smoke verify backup restore demo

bootstrap:
	@bash infra/scripts/bootstrap.sh

up:
	@$(COMPOSE) --profile $(PROFILE) up -d --build
	@$(COMPOSE) --profile $(PROFILE) run --rm api alembic upgrade head

down:
	@$(COMPOSE) --profile full down --remove-orphans

reset:
	@bash infra/scripts/reset.sh

reset-test:
	@RESET_TEST_ONLY=1 bash infra/scripts/reset.sh

lint:
	@$(UV) run ruff check apps packages simulator/demo-service simulator/scripts simulator/traffic
	@$(UV) run ruff format --check apps packages simulator/demo-service simulator/scripts simulator/traffic
	@$(PNPM) lint

format:
	@$(UV) run ruff format apps packages simulator/demo-service simulator/scripts simulator/traffic
	@$(UV) run ruff check --fix apps packages simulator/demo-service simulator/scripts simulator/traffic
	@$(PNPM) format

typecheck:
	@$(UV) run mypy apps/api/app packages
	@cd simulator/demo-service && $(UV) run mypy demo_service
	@$(PNPM) typecheck

test:
	@cd apps/api && $(UV) run pytest
	@cd apps/worker && $(UV) run pytest
	@cd packages/agent && $(UV) run pytest
	@cd packages/tools && $(UV) run pytest
	@cd simulator/demo-service && $(UV) run pytest
	@$(PNPM) test

migrate:
	@$(COMPOSE) --profile $(PROFILE) up -d postgres
	@$(COMPOSE) --profile $(PROFILE) run --rm api alembic upgrade head

compose-validate:
	@$(COMPOSE) --profile minimal config >/dev/null
	@$(COMPOSE) --profile ai config >/dev/null
	@$(COMPOSE) --profile observability config >/dev/null
	@$(COMPOSE) --profile sim config >/dev/null
	@$(COMPOSE) --profile full config >/dev/null
	@! $(COMPOSE) --profile minimal config --services | grep -E 'ollama|prometheus|grafana|loki|tempo|otel-collector|langfuse|demo-service|traffic-generator'

build:
	@$(COMPOSE) --profile minimal build

security-scan:
	@bash infra/scripts/security-scan.sh

smoke:
	@bash infra/scripts/smoke.sh

seed-users:
	@$(COMPOSE) --profile $(PROFILE) run --rm api python -m app.cli.seed_users

seed-services:
	@$(COMPOSE) --profile $(PROFILE) run --rm api python -m app.cli.seed_services

seed-perf:
	@$(COMPOSE) --profile $(PROFILE) run --rm api python -m app.cli.seed_perf

ingest-runbooks:
	@$(COMPOSE) --profile $(PROFILE) run --rm api python -m app.cli.ingest_runbooks

sim-seed:
	@cd simulator/demo-service && $(UV) run python ../scripts/seed.py

sim-reset:
	@cd simulator/demo-service && $(UV) run python ../scripts/reset.py

sim-scenario:
	@test -n "$(ID)" || (echo "Usage: make sim-scenario ID=SCN-003-db-pool-exhaustion" && exit 1)
	@curl -sS -X POST "http://127.0.0.1:8080/sim/scenarios/$(ID)/activate" \
		-H "Content-Type: application/json" \
		-d "{\"seed\": $${SEED:-42}, \"mode\": \"$${MODE:-live}\"}" | python -m json.tool

eval:
	@bash infra/scripts/eval.sh

eval-smoke:
	@EVAL_SMOKE=true bash infra/scripts/eval.sh

verify:
	@bash infra/scripts/verify.sh

backup:
	@bash infra/scripts/backup.sh

restore:
	@test -n "$(DIR)" || (echo "Usage: make restore DIR=backups/YYYYMMDD-HHMMSS" && exit 1)
	@bash infra/scripts/restore.sh "$(DIR)"

demo:
	@bash infra/scripts/demo.sh
