"""Best-effort artifact persistence for remote benchmark jobs."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from inflab.config import AppSettings
from inflab.db.models import Artifact, JobRecord
from inflab.object_store import S3ObjectStore
from inflab.schemas import BenchmarkCommandPlan


def persist_remote_benchmark_artifacts(
    session: Session,
    *,
    settings: AppSettings,
    job: JobRecord,
    plan: BenchmarkCommandPlan,
    remote_result: dict[str, Any],
) -> list[dict[str, str]]:
    store = S3ObjectStore(settings.object_storage)
    refs: list[dict[str, str]] = []
    entries = [
        {
            "kind": "log",
            "name": f"benchmark-{job.id}.log",
            "content": "\n".join(str(line) for line in remote_result.get("logs", [])),
            "content_type": "text/plain",
        },
        {
            "kind": "metrics",
            "name": f"benchmark-{job.id}-raw-result.txt",
            "content": str(remote_result.get("raw_result") or remote_result.get("stdout") or ""),
            "content_type": "text/plain",
        },
    ]
    for entry in entries:
        content = entry["content"]
        if not content:
            continue
        key = f"benchmarks/{job.id}/{entry['name']}"
        try:
            stored = store.upload_bytes(
                key,
                content.encode(),
                content_type=entry["content_type"],
            )
        except Exception as exc:
            job.logs = [*(job.logs or []), f"artifact upload failed for {entry['name']}: {exc}"]
            continue
        artifact = Artifact(
            kind=entry["kind"],
            name=entry["name"],
            uri=stored.uri,
            sha256=stored.sha256,
            size_bytes=stored.size_bytes,
            metadata_json={
                "job_id": job.id,
                "result_path": plan.result_path,
                "presigned_url": stored.presigned_url,
            },
        )
        session.add(artifact)
        session.flush()
        refs.append({"artifact_id": artifact.id, "kind": artifact.kind, "uri": artifact.uri})
    return refs
