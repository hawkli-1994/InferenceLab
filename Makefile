SHELL := /bin/sh

UV ?= uv
PNPM ?= pnpm
NPM ?= npm
PM2 ?= pm2
PM2_CONFIG ?= deploy/pm2/ecosystem.config.cjs

.PHONY: help deps install install-backend install-frontend install-pm2 install-tools
.PHONY: test lint format-check quality frontend-build
.PHONY: pm2-start pm2-start-all pm2-stop pm2-restart pm2-reload pm2-delete pm2-save
.PHONY: pm2-worker pm2-status pm2-logs status backend frontend logs-api logs-ui restart-api restart-ui

help:
	@printf '%s\n' 'InferenceLab targets:'
	@printf '%s\n' '  make install        Install backend, frontend, and PM2 dependencies'
	@printf '%s\n' '  make test           Run backend tests'
	@printf '%s\n' '  make lint           Run ruff checks'
	@printf '%s\n' '  make frontend-build Build the Vite frontend'
	@printf '%s\n' '  make pm2-start      Start local API and frontend with PM2'
	@printf '%s\n' '  make pm2-start-all  Start API, frontend, and RQ worker with PM2'
	@printf '%s\n' '  make pm2-stop       Stop PM2-managed InferenceLab processes'
	@printf '%s\n' '  make status         Show PM2 process status'
	@printf '%s\n' '  make logs-api       Tail backend API logs'
	@printf '%s\n' '  make logs-ui        Tail frontend logs'

deps: install

install: install-backend install-frontend install-pm2

install-backend:
	$(UV) sync --all-extras --dev

install-frontend:
	@if ! command -v $(PNPM) >/dev/null 2>&1; then \
		echo "$(PNPM) is required. Install it with corepack or npm before running this target."; \
		exit 1; \
	fi
	cd frontend && $(PNPM) install

install-pm2:
	@if command -v $(PM2) >/dev/null 2>&1; then \
		$(PM2) --version; \
	else \
		$(NPM) install -g pm2; \
	fi

install-tools: install-pm2

test:
	$(UV) run pytest

lint:
	$(UV) run ruff check .

format-check:
	$(UV) run ruff format --check .

frontend-build:
	cd frontend && $(PNPM) build

quality: lint format-check test frontend-build

pm2-start:
	$(PM2) startOrRestart $(PM2_CONFIG) --only inflab-api --update-env
	$(PM2) startOrRestart $(PM2_CONFIG) --only inflab-frontend --update-env

pm2-start-all:
	$(PM2) startOrRestart $(PM2_CONFIG) --update-env

pm2-worker:
	$(PM2) startOrRestart $(PM2_CONFIG) --only inflab-worker --update-env

pm2-stop:
	-$(PM2) stop inflab-api
	-$(PM2) stop inflab-frontend
	-$(PM2) stop inflab-worker

pm2-restart:
	$(PM2) restart inflab-api --update-env
	$(PM2) restart inflab-frontend --update-env

pm2-reload:
	$(PM2) reload inflab-api --update-env
	$(PM2) reload inflab-frontend --update-env

pm2-delete:
	-$(PM2) delete inflab-api
	-$(PM2) delete inflab-frontend
	-$(PM2) delete inflab-worker

pm2-save:
	$(PM2) save

pm2-status status:
	$(PM2) status

pm2-logs:
	$(PM2) logs

backend:
	$(PM2) startOrRestart $(PM2_CONFIG) --only inflab-api --update-env

frontend:
	$(PM2) startOrRestart $(PM2_CONFIG) --only inflab-frontend --update-env

logs-api:
	$(PM2) logs inflab-api

logs-ui:
	$(PM2) logs inflab-frontend

restart-api:
	$(PM2) restart inflab-api --update-env

restart-ui:
	$(PM2) restart inflab-frontend --update-env
