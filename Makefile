SHELL := /bin/bash
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
COMPOSE := docker compose
PROFILE ?= minimal
UV := uv
PNPM := $(if $(wildcard node_modules/.bin/pnpm),./node_modules/.bin/pnpm,$(shell command -v pnpm 2>/dev/null || echo npx\ --yes\ pnpm@9))

.PHONY: bootstrap up down reset lint format typecheck test migrate compose-validate build security-scan smoke seed-users seed-services seed-perf

bootstrap:
	@bash infra/scripts/bootstrap.sh

up:
	@$(COMPOSE) --profile $(PROFILE) up -d --build
	@$(COMPOSE) --profile $(PROFILE) run --rm api alembic upgrade head

down:
	@$(COMPOSE) --profile full down --remove-orphans

reset:
	@bash infra/scripts/reset.sh

lint:
	@$(UV) run ruff check apps packages
	@$(UV) run ruff format --check apps packages
	@$(PNPM) lint

format:
	@$(UV) run ruff format apps packages
	@$(UV) run ruff check --fix apps packages
	@$(PNPM) format

typecheck:
	@$(UV) run mypy apps/api/app packages
	@$(PNPM) typecheck

test:
	@cd apps/api && $(UV) run pytest
	@cd apps/worker && $(UV) run pytest
	@$(PNPM) test

migrate:
	@cd apps/api && $(UV) run alembic upgrade head

compose-validate:
	@$(COMPOSE) --profile minimal config >/dev/null
	@$(COMPOSE) --profile ai config >/dev/null
	@$(COMPOSE) --profile observability config >/dev/null
	@$(COMPOSE) --profile full config >/dev/null
	@! $(COMPOSE) --profile minimal config | grep -E 'ollama|prometheus|grafana|loki|tempo|otel-collector|langfuse'

build:
	@$(COMPOSE) --profile minimal build

security-scan:
	@bash infra/scripts/security-scan.sh

smoke:
	@bash infra/scripts/smoke.sh

seed-users:
	@cd apps/api && $(UV) run python -m app.cli.seed_users

seed-services:
	@cd apps/api && $(UV) run python -m app.cli.seed_services

seed-perf:
	@cd apps/api && $(UV) run python -m app.cli.seed_perf
