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

The default business loop uses dry-run/fake execution so it can run safely in local tests. Real
SSH, RQ, S3/MinIO, benchmark execution, and external LLM providers are implemented as explicit
opt-in paths.

## Real SSH Path

`AsyncSSHExecutor` is implemented for manual opt-in machine operations. It supports:

- password, PEM private-key, and explicit `ssh_agent` authentication;
- strict or permissive host-key policy from `INFLAB_SSH_KNOWN_HOSTS_POLICY`;
- remote command execution with cwd/env/sudo/timeout;
- SFTP upload and download.

`POST /api/v1/machines/{machine_id}/probe?dry_run=false` probes hardware/system/container/GPU/
network/disk data through SSH. `POST /api/v1/machines/{machine_id}/bootstrap` uses the fake
executor when `dry_run=true`; when `dry_run=false`, it decrypts the machine credential and runs
B1-B7 through AsyncSSH.

`POST /api/v1/machines/{machine_id}/discovery-sessions?dry_run=false` is the safer first real SSH
path. It only runs fixed allowlisted read-only commands and records command output, profile,
verdict, and blockers. It never writes files, uploads data, or uses sudo.

This path is not covered by required real-machine E2E yet; unit tests mock AsyncSSH and verify the
command, credential, timeout, SFTP, and streaming behavior. A read-only opt-in smoke test is
available with:

```bash
INFLAB_REAL_SSH_TARGET=rx@172.18.1.239 uv run pytest backend/tests/test_real_ssh_opt_in.py
```

The smoke test only runs the safe discovery allowlist; it does not write files, upload data, use
sudo, or change machine configuration.

## Real Benchmark and Artifact Paths

- `POST /api/v1/benchmarks/plan` builds vLLM and SGLang command plans.
- `POST /api/v1/benchmarks/jobs` with `execution_mode=remote_inline` runs the benchmark over
  AsyncSSH in the API process.
- `POST /api/v1/benchmarks/jobs` with `execution_mode=remote_rq` enqueues an RQ job for the
  worker.
- `POST /api/v1/models/{model_id}/distribute` performs rsync/NFS/MinIO/HuggingFace/ModelScope
  distribution commands when `dry_run=false`.
- `POST /api/v1/artifacts/upload-text` and report PDF/DOCX downloads upload bytes to S3-compatible
  storage.

The LLM candidate provider uses LiteLLM and is disabled by default. Configure `INFLAB_LLM_PROVIDER`,
`INFLAB_LLM_MODEL`, `INFLAB_LLM_API_KEY`, and optionally `INFLAB_LLM_BASE_URL` to enable it.
