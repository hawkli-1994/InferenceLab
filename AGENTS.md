# AGENTS.md

This file is the primary operating guide for Codex and similar coding agents working in this repository. Treat it as the repository README for agents.

## Project Context

InferenceLab / ModelBench Agent is an internal R&D platform for automated model inference benchmarking, tuning, and report generation on AI servers.

Read these documents before making architectural or product-shaping changes:

- `modelbench_agent_requirements_2.md`: product requirements and MVP scope.
- `modelbench_agent_tech_selection.md`: technical decisions, non-goals, and 10-week implementation map.
- `docs/agent_harness.md`: how this repository's Codex-oriented instruction harness is organized.

The product philosophy is intentionally pragmatic: this is an internal workshop-grade tool, not an enterprise SaaS platform. Prefer fewer services, explicit data records, reproducible experiments, and useful error messages.

## Current Implementation State

The repository currently contains requirements, technical selection docs, and agent harness files. Application code should follow the structure proposed in `modelbench_agent_tech_selection.md` unless a later committed architecture document supersedes it.

Expected top-level structure as implementation begins:

```text
backend/
frontend/
playbooks/
deploy/
docs/
```

Do not create a competing structure without updating the docs and explaining the reason.

## Core Technical Direction

Default stack:

- Backend API: Python 3.12+, FastAPI, Pydantic, SQLAlchemy 2, Alembic.
- Worker queue: Redis + RQ.
- Remote execution: AsyncSSH + rsync + idempotent Step model.
- Database: PostgreSQL.
- Artifacts: MinIO or S3-compatible object storage.
- Frontend: React + Vite + TypeScript + TanStack Query + ECharts.
- Reports: Jinja2 + Markdown + Pandoc + Typst.
- Deployment: Docker Compose single instance for MVP.

Technologies explicitly deferred unless the user asks otherwise:

- Kubernetes.
- Temporal.
- Celery.
- Airflow.
- LangChain / LlamaIndex.
- TimescaleDB.
- Plugin hot loading.

## Design Invariants

Preserve these constraints in code and docs:

- `container` and `bare_metal` runtime modes are first-class and must not become two unrelated code paths.
- Every experiment must be reproducible from recorded machine profile, model hash, runtime mode, framework version, framework params, prompt dataset, and launch command.
- Remote machine changes must be modeled as explicit steps with `detect`, `apply`, and `verify` phases.
- Remote step output must record command, exit code, stdout/stderr artifact location, changed files, snapshots, and failure hints.
- PostgreSQL stores queryable facts and summaries; large logs, raw metrics, reports, and snapshots live in object storage with database references.
- Default tests must not require real SSH machines, GPUs, NAS, Docker daemon mutation, or external LLM calls.
- Integration tests that touch real machines or external services must be opt-in and clearly marked.

## Coding Rules

- Keep implementation close to the documented MVP. Avoid broad framework introductions and speculative abstractions.
- Use Pydantic models for external API payloads, plugin specs, benchmark results, and LLM structured outputs.
- Keep shell commands in remote executor modules, not scattered across API handlers or workers.
- Prefer structured parsers or typed models over ad hoc string handling when outputs are important for reports.
- For plugin interfaces, use Python Protocols or abstract base classes plus explicit registries. Do not implement runtime plugin hot loading in MVP.
- For benchmark and tuning logic, separate deterministic validation/pruning from LLM candidate generation.
- Never let an LLM-generated parameter set execute before schema validation and heuristic safety checks.
- Avoid storing secrets in logs, reports, fixtures, or committed config.

## Test And Quality Commands

Use these once the corresponding code exists:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

For frontend code once `frontend/` exists:

```bash
pnpm test
pnpm lint
pnpm build
```

If these commands are not yet available because the scaffold has not been created, say that clearly in the final response instead of pretending they ran.

## Documentation Rules

Update documentation when a change affects:

- architecture or service boundaries;
- plugin contracts;
- runtime mode behavior;
- experiment schema or reproducibility guarantees;
- bootstrap/provisioning behavior;
- development or test commands.

Keep `AGENTS.md` concise and durable. Put longer rationale in `docs/`.

## GitHub Workflow

- Default branch is `main`.
- Keep commits focused.
- Do not rewrite history or force-push unless the user explicitly asks.
- Before pushing, run the relevant tests/checks when they exist.
- If a change intentionally skips tests, state the reason in the final response.
