# Backend API Summary

The MVP API is exposed under `/api/v1` and is documented by FastAPI at `/openapi.json`.

## Implemented Surfaces

- Machines: CRUD, dry-run or real SSH probe, snapshots, credential masking.
- Discovery: safe read-only allowlist sessions with machine profile, readiness verdict, blockers, and command logs.
- Bootstrap: Pi environment workflow, explicit scripted Full/standard/minimal/custom profiles, B1-B7 dry-run step results, opt-in real SSH execution, rerun single module.
- Models and images: registry records, SHA256 metadata, dry-run plans and opt-in distribution for rsync/NFS/MinIO/HuggingFace/ModelScope.
- Artifacts: report/log/snapshot/metrics/model/image references plus S3-compatible text upload.
- Jobs: synchronous fake queue and Redis/RQ queue adapter with status, progress, logs, and result.
- Benchmarks: RunSpec, fake benchmark job, normalized metrics, vLLM/SGLang command planning, opt-in remote inline/RQ execution.
- Experiments: standard/intelligent mode candidate planning, create/query/cancel/copy/compare, trials, run-log aggregation, metrics, chart data, company-format table reports.
- Plugins: runtime/framework/driver/model plugin registry.
- AutoResearch: `GET /api/v1/autoresearch/integration-plan` exposes the Deli_AutoResearch intelligent-mode protocol boundary.
- Agent settings: `GET/PUT /api/v1/agent-settings` persists LLM provider and Pi executor configuration; `/validate` checks a draft config without saving secrets.
- Agent executors: `GET /api/v1/agent-executors/pi/plan` and `/prompt` expose the effective Pi worker executor plan for intelligent mode.
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

## Environment Setup Strategies

`POST /api/v1/machines/{machine_id}/discovery-sessions` runs a safe discovery session before
environment setup. `dry_run=true` returns a deterministic fake profile for local tests. With
`dry_run=false`, the backend connects through the configured SSH credential and runs only the
fixed read-only allowlist. The response includes:

- `verdict`: `ready`, `partially_ready`, or `blocked`;
- `blockers`: typed warning/blocking issues with evidence command ids;
- `profile`: structured machine profile plus fingerprint;
- `command_results`: command, exit code, stdout/stderr for every allowlisted command.

`GET /api/v1/discovery-sessions` lists persisted discovery sessions. Sessions are stored as
`SAFE_DISCOVERY` bootstrap runs plus machine snapshots, so they are auditable with the existing
run model.

`POST /api/v1/machines/{machine_id}/bootstrap` accepts `strategy`. Omit it to use
`pi_workflow`; send `strategy=scripted` only for the fixed B1-B7 baseline. Unknown fields are
rejected, so the removed `manual_environment` bypass cannot be used accidentally.

- `strategy=pi_workflow`: preferred path for real environments. The backend builds a generic
  discover/plan/apply/verify/record workflow prompt and hands it to the configured Pi agent.
  `dry_run=true` records the prompt and Pi executor plan without executing Pi; `dry_run=false`
  runs the configured Pi command with the prompt on stdin. This path records `PI_ENV_WORKFLOW`
  and does not execute B1-B7 scripted commands.
- `strategy=scripted`: B1-B7 baseline. `dry_run=true` uses `FakeExecutor`, suitable for default
  tests and demos. `dry_run=false` decrypts the stored machine credential and uses
  `AsyncSSHExecutor`.

The workbench exposes both paths as a dynamic setup-mode selector. Pi Workflow is the default, and
Scripted Baseline keeps a reproducible fixed profile. A Pi workflow dry-run marks the machine
`agent_workflow_planned`; only successful non-dry-run execution marks it `ready`.

The real SSH executor supports remote command execution with cwd/env/sudo/timeout plus SFTP
upload/download. Password, PEM private-key, and explicit `ssh_agent` credentials are supported.
Host-key behavior follows `INFLAB_SSH_KNOWN_HOSTS_POLICY`: `permissive` passes `known_hosts=None`;
`strict` uses AsyncSSH's normal known-hosts behavior.

`ssh_agent` is explicit: a machine must be created with
`{"credential":{"credential_type":"ssh_agent"}}`. A machine with no credential still rejects
`dry_run=false` SSH operations, so the API does not accidentally try the backend process agent
against arbitrary hosts.

This is implementation-complete for manual smoke tests but intentionally lacks required
real-machine E2E in this repository state. The opt-in read-only discovery smoke command is:

```bash
INFLAB_REAL_SSH_TARGET=rx@172.18.1.239 uv run pytest backend/tests/test_real_ssh_opt_in.py
```

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

## Experiment Modes

Experiment planning accepts `mode`:

- `standard`: default. Uses a deterministic software-driven matrix inspired by `llm_test_tools`,
  with paired parallel/request points and progressive short-to-long context ordering.
- `intelligent`: enables Agent/LLM candidate planning and reserves the Deli_AutoResearch protocol
  boundary for long-horizon orchestration.

`GET /api/v1/autoresearch/integration-plan` returns the intended state files, watchdog,
stall-detection, gate commands, and Pi worker executor metadata for the intelligent mode. The
protocol is metadata-only in this slice; standard mode does not depend on it.

The workbench exposes an Agent Settings panel beside experiment creation. It can configure:

- LLM provider: disabled, OpenAI-compatible, or Anthropic;
- Base URL, model, and encrypted API key;
- Pi agent enabled state, command, work dir, max rounds, and timeout;
- config validation plus the current Pi executor plan and worker prompt preview.

Pi agent is modeled as a bounded executor. It has two product roles: environment provisioning
workflow execution and intelligent-mode worker iterations. It must not replace the standard-mode
software matrix runner.

- `GET /api/v1/agent-executors/pi/plan`: provider, command, work dir, round cap, timeout, and boundary notes.
- `GET /api/v1/agent-executors/pi/prompt`: bounded one-iteration worker prompt aligned with Deli_AutoResearch.
- `GET /api/v1/agent-settings`: effective settings, masked API key status, Pi plan, and prompt.
- `PUT /api/v1/agent-settings`: persists UI settings; blank API key preserves the existing key,
  and `clear_api_key=true` removes it.
- `POST /api/v1/agent-settings/validate`: validates a draft settings payload without saving it.

## LLM Candidate Provider

Experiment planning can merge deterministic candidates with LiteLLM-generated candidates in
`mode=intelligent`. The provider is disabled by default. Configure through Agent Settings in the
workbench, or use environment variables as process defaults:

- `INFLAB_LLM_PROVIDER=openai_compatible` or `anthropic`;
- `INFLAB_LLM_MODEL`;
- `INFLAB_LLM_API_KEY`;
- optional `INFLAB_LLM_BASE_URL` for OpenAI-compatible endpoints.

Returned parameter sets are parsed as JSON, validated as `FrameworkParams`, and then passed through
the existing heuristic pruning before any launch command is generated.

## Company-Format Result Table

After an experiment has completed trials and written metrics, the default result table is available
through:

- `GET /api/v1/experiments/{experiment_id}/company-report`
- `GET /api/v1/experiments/{experiment_id}/company-report/export`

The JSON endpoint returns `columns` plus ordered `rows`. The CSV export uses the same columns in this
exact order:

```text
测试时间,机型,GPU,模型,精度,物理卡数,逻辑卡数,模式,请求并发数,输入,输出,总输入,总输出,请求吞吐,输出吞吐,总吞吐,首Token延时(ms),每Token延时(ms),总耗时(s),平均每用户输出吞吐,备注
```

Rows are derived from the recorded experiment, machine profile, model record, trial params, benchmark
result, and metrics summary. Missing workload facts fall back to the current default synthetic
benchmark workload so default tests remain self-contained.

## Current Forward Slice

The workbench now has a database-backed interactive launch path:

- seed demo data into the database from `POST /api/v1/dev/seed-demo-data` or the `Seed DB` button;
- register a demo model from the frontend;
- create/probe a machine, run Safe Discovery, then run Pi workflow or explicitly selected scripted bootstrap;
- distribute a model to the selected machine;
- configure Agent Settings for Pi workflow and intelligent mode without affecting standard mode;
- preview Agent tuning candidates through `POST /api/v1/experiments/plan`;
- create an experiment with validated candidate params and generated trial logs;
- submit fake, remote inline, or remote RQ benchmark jobs and poll job logs;
- inspect `GET /api/v1/experiments/{experiment_id}/run-log`;
- inspect the default company-format table result and export it as CSV;
- list generated reports through `GET /api/v1/reports`;
- request report downloads and view artifact rows.

The frontend no longer imports local mock data or falls back to in-browser mock responses. Empty
states come from an empty backend database, and demo states come from seeded backend records.

## E2E Status

This implementation intentionally does not enable true backend E2E. The marker file
`tests/e2e/backend_e2e_enabled` is absent, so the GitHub Actions workflow remains in preflight mode.
Per the latest task direction, this remains intentionally bypassed while local/fake features move forward.
