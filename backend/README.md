# InferenceLab Backend

MVP backend for the ModelBench Agent control plane.

## Local Commands

Run from the repository root or from this directory:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

The default test suite is in-process only. It must not require real SSH machines, GPUs,
NAS mounts, Docker daemon mutation, or external LLM calls.

## API

- Health: `GET /healthz`
- OpenAPI: `GET /openapi.json`
- MVP API: `/api/v1/*`

The default business loop uses a fake queue, fake executor, fake plugins, and mock benchmark
results so it can run safely in local tests.
