# Backend API Summary

The MVP API is exposed under `/api/v1` and is documented by FastAPI at `/openapi.json`.

## Implemented Surfaces

- Machines: CRUD, dry-run or real SSH probe, snapshots, credential masking.
- Bootstrap: Full/standard/minimal/custom profiles, B1-B7 dry-run step results, manual opt-in real SSH execution, rerun single module.
- Models and images: registry records, SHA256 metadata, dry-run plans and opt-in distribution for rsync/NFS/MinIO/HuggingFace/ModelScope.
- Artifacts: report/log/snapshot/metrics/model/image references plus S3-compatible text upload.
- Jobs: synchronous fake queue and Redis/RQ queue adapter with status, progress, logs, and result.
- Benchmarks: RunSpec, fake benchmark job, normalized metrics, vLLM/SGLang command planning, opt-in remote inline/RQ execution.
- Experiments: candidate planning, create/query/cancel/copy/compare, trials, run-log aggregation, metrics, chart data.
- Plugins: runtime/framework/driver/model plugin registry.
- Reports: list/query, Markdown rendering, PDF/DOCX export through Pandoc/Typst when installed, artifact metadata, redaction.
- Dev data: `POST /api/v1/dev/seed-demo-data` creates idempotent database-backed demo records.

## Benchmark Command Planning

`POST /api/v1/benchmarks/plan` generates a command plan without executing real inference. For vLLM
it emits:

- `vllm bench serve` with `--save-result`, `--result-dir`, and `--result-filename`;
- `vllm bench throughput` with `--output-json`;
- the corresponding model serve command for online serving tests.

For SGLang it emits `python -m sglang.bench_serving --backend sglang ...` with the same model,
dataset, prompt count, token length, and request-rate inputs.

Execution is separate:

- `execution_mode=fake`: fake benchmark result for local tests and demos.
- `execution_mode=remote_inline`: AsyncSSH runs the planned command and streams lines into the job
  logs returned by `GET /api/v1/jobs/{job_id}/logs`.
- `execution_mode=remote_rq`: stores the job in the database and enqueues the worker function in
  Redis/RQ.

Remote benchmark logs and raw result text are uploaded as best-effort S3 artifacts and linked from
the job result. If object storage is unavailable, the benchmark result is preserved and the artifact
upload failure is appended to the job logs.

Default tests still do not install vLLM/SGLang, start a model, touch GPUs, or open SSH connections.

## Real SSH Bootstrap

`POST /api/v1/machines/{machine_id}/bootstrap` selects execution mode from `dry_run`:

- `dry_run=true`: uses `FakeExecutor`, suitable for default tests and demos.
- `dry_run=false`: decrypts the stored machine credential and uses `AsyncSSHExecutor`.

The real SSH executor supports remote command execution with cwd/env/sudo/timeout plus SFTP
upload/download. Password and PEM private-key credentials are supported. Host-key behavior follows
`INFLAB_SSH_KNOWN_HOSTS_POLICY`: `permissive` passes `known_hosts=None`; `strict` uses AsyncSSH's
normal known-hosts behavior.

This is implementation-complete for manual smoke tests but intentionally lacks real-machine E2E in
this repository state.

## Model Distribution and Artifacts

`POST /api/v1/models/{model_id}/distribute` accepts:

```json
{
  "machine_id": "machine-id",
  "target_path": "/data/models/qwen3-32b",
  "dry_run": false
}
```

When `dry_run=false`, the backend runs the source-specific command through AsyncSSH. rsync uses
`--partial --checksum`, HuggingFace uses `huggingface-cli download --resume-download`, and MinIO
uses `aws s3 sync`.

`POST /api/v1/artifacts/upload-text` writes report/log/snapshot/metrics text content to the
configured S3-compatible bucket and stores an artifact row with URI, size, hash, and optional
presigned URL metadata.

## LLM Candidate Provider

Experiment planning can merge deterministic candidates with LiteLLM-generated candidates. The
provider is disabled by default. Configure:

- `INFLAB_LLM_PROVIDER=openai_compatible` or `anthropic`;
- `INFLAB_LLM_MODEL`;
- `INFLAB_LLM_API_KEY`;
- optional `INFLAB_LLM_BASE_URL` for OpenAI-compatible endpoints.

Returned parameter sets are parsed as JSON, validated as `FrameworkParams`, and then passed through
the existing heuristic pruning before any launch command is generated.

## Current Forward Slice

The workbench now has a database-backed interactive launch path:

- seed demo data into the database from `POST /api/v1/dev/seed-demo-data` or the `Seed DB` button;
- register a demo model from the frontend;
- create/probe a machine and run dry-run or real SSH bootstrap;
- distribute a model to the selected machine;
- preview Agent tuning candidates through `POST /api/v1/experiments/plan`;
- create an experiment with validated candidate params and generated trial logs;
- submit fake, remote inline, or remote RQ benchmark jobs and poll job logs;
- inspect `GET /api/v1/experiments/{experiment_id}/run-log`;
- list generated reports through `GET /api/v1/reports`;
- request report downloads and view artifact rows.

The frontend no longer imports local mock data or falls back to in-browser mock responses. Empty
states come from an empty backend database, and demo states come from seeded backend records.

## E2E Status

This implementation intentionally does not enable true backend E2E. The marker file
`tests/e2e/backend_e2e_enabled` is absent, so the GitHub Actions workflow remains in preflight mode.
Per the latest task direction, this remains intentionally bypassed while local/fake features move forward.
