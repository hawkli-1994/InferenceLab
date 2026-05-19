"""Synchronous fake queue with an RQ-compatible shape for tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from inflab.db.models import JobRecord


class FakeQueue:
    def enqueue(
        self,
        session: Session,
        job_type: str,
        handler: Callable[[], dict[str, Any]],
    ) -> JobRecord:
        job = JobRecord(job_type=job_type, status="running", progress=0.1, logs=["job started"])
        session.add(job)
        session.flush()
        try:
            result = handler()
            job.status = "succeeded"
            job.progress = 1.0
            job.logs = [*job.logs, "job completed"]
            job.result = result
        except Exception as exc:
            job.status = "failed"
            job.progress = 1.0
            job.logs = [*job.logs, "job failed"]
            job.error = str(exc)
        session.commit()
        session.refresh(job)
        return job


fake_queue = FakeQueue()
