"""Job queue adapters."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from redis import Redis
from rq import Queue
from sqlalchemy.orm import Session

from inflab.config import RedisSettings
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


class RQQueue:
    def __init__(self, settings: RedisSettings) -> None:
        self.settings = settings
        self.redis = Redis.from_url(settings.url)
        self.queue = Queue(settings.queue_name, connection=self.redis)

    def enqueue_importable(
        self,
        session: Session,
        job_type: str,
        function_path: str,
        *args: object,
        **kwargs: object,
    ) -> JobRecord:
        job = JobRecord(job_type=job_type, status="queued", progress=0.0, logs=["job queued"])
        session.add(job)
        session.commit()
        session.refresh(job)
        rq_job = self.queue.enqueue(function_path, job.id, *args, **kwargs)
        job.result = {"rq_job_id": rq_job.id}
        session.commit()
        session.refresh(job)
        return job
