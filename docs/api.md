# Backend API Summary

The MVP API is exposed under `/api/v1` and is documented by FastAPI at `/openapi.json`.

## Implemented Surfaces

- Machines: CRUD, fake probe, snapshots, credential masking.
- Bootstrap: Full/standard/minimal/custom profiles, B1-B7 dry-run step results, rerun single module.
- Models and images: registry records, SHA256 metadata, distribution-plan interface for rsync/NFS/MinIO/HuggingFace/ModelScope.
- Artifacts: report/log/snapshot/metrics/model/image references.
- Jobs: synchronous fake queue with status, progress, logs, and result.
- Benchmarks: RunSpec, fake benchmark job, normalized metrics, vLLM benchmark command planning.
- Experiments: candidate planning, create/query/cancel/copy/compare, trials, run-log aggregation, metrics, chart data.
- Plugins: runtime/framework/driver/model plugin registry.
- Reports: list/query, Markdown rendering, PDF/DOCX download stubs, artifact metadata, redaction.
- Dev data: `POST /api/v1/dev/seed-demo-data` creates idempotent database-backed demo records.

## Benchmark Command Planning

`POST /api/v1/benchmarks/plan` generates a command plan without executing real inference.
For vLLM it emits:

- `vllm bench serve` with `--save-result`, `--result-dir`, and `--result-filename`;
- `vllm bench throughput` with `--output-json`;
- the corresponding model serve command for online serving tests.

This is intentionally command planning only. Default tests still do not install vLLM, start a model,
touch GPUs, or open SSH connections.

## Current Forward Slice

The workbench now has a database-backed interactive launch path:

- seed demo data into the database from `POST /api/v1/dev/seed-demo-data` or the `Seed DB` button;
- register a demo model from the frontend;
- create/probe a machine and run dry-run bootstrap;
- preview Agent tuning candidates through `POST /api/v1/experiments/plan`;
- create an experiment with validated candidate params and generated trial logs;
- inspect `GET /api/v1/experiments/{experiment_id}/run-log`;
- list generated reports through `GET /api/v1/reports`.

The frontend no longer imports local mock data or falls back to in-browser mock responses. Empty
states come from an empty backend database, and demo states come from seeded backend records.

## E2E Status

This implementation intentionally does not enable true backend E2E. The marker file
`tests/e2e/backend_e2e_enabled` is absent, so the GitHub Actions workflow remains in preflight mode.
Per the latest task direction, this remains intentionally bypassed while local/fake features move forward.
