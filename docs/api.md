# Backend API Summary

The MVP API is exposed under `/api/v1` and is documented by FastAPI at `/openapi.json`.

## Implemented Surfaces

- Machines: CRUD, fake probe, snapshots, credential masking.
- Bootstrap: Full/standard/minimal/custom profiles, B1-B7 dry-run step results, rerun single module.
- Models and images: registry records, SHA256 metadata, distribution-plan interface for rsync/NFS/MinIO/HuggingFace/ModelScope.
- Artifacts: report/log/snapshot/metrics/model/image references.
- Jobs: synchronous fake queue with status, progress, logs, and result.
- Benchmarks: RunSpec, fake benchmark job, normalized metrics.
- Experiments: create/query/cancel/copy/compare, trials, metrics, chart data.
- Plugins: runtime/framework/driver/model plugin registry.
- Reports: Markdown rendering, PDF/DOCX download stubs, artifact metadata, redaction.

## E2E Status

This implementation intentionally does not enable true backend E2E. The marker file
`tests/e2e/backend_e2e_enabled` is absent, so the GitHub Actions workflow remains in preflight mode.
