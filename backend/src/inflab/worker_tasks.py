"""Importable RQ task entry points."""

from __future__ import annotations

import asyncio

from sqlalchemy.orm import Session

from inflab.api.v1 import _ssh_executor_for_machine
from inflab.benchmark import build_benchmark_command_plan, run_remote_benchmark
from inflab.benchmark_artifacts import persist_remote_benchmark_artifacts
from inflab.config import get_settings
from inflab.db import configure_database
from inflab.db.models import JobRecord, Machine, ModelRecord
from inflab.db.session import get_session
from inflab.schemas import BenchmarkPlanCreate


def _session() -> Session:
    configure_database(get_settings().database.url)
    generator = get_session()
    return next(generator)


def run_remote_benchmark_job(job_id: str, payload: dict) -> dict:
    settings = get_settings()
    session = _session()
    job = session.get(JobRecord, job_id)
    if job is None:
        raise RuntimeError(f"job {job_id} not found")
    job.status = "running"
    job.progress = 0.1
    job.logs = [*job.logs, "worker started"]
    session.commit()

    try:
        plan_payload = BenchmarkPlanCreate.model_validate(payload)
        machine = session.get(Machine, plan_payload.run_spec.machine_id)
        model = session.get(ModelRecord, plan_payload.run_spec.model_id)
        if machine is None or model is None:
            raise RuntimeError("machine or model not found")
        plan = build_benchmark_command_plan(plan_payload, model_path=model.cache_path)
        result = asyncio.run(run_remote_benchmark(_ssh_executor_for_machine(machine), plan))
        job.status = "succeeded" if result.get("status") == "succeeded" else "failed"
        job.progress = 1.0
        job.logs = [*job.logs, *[str(line) for line in result.get("logs", [])], "worker completed"]
        job.result = {"plan": plan.model_dump(mode="json"), "remote_result": result}
        job.error = (
            None if job.status == "succeeded" else str(result.get("error") or result.get("stderr"))
        )
        artifact_refs = persist_remote_benchmark_artifacts(
            session,
            settings=settings,
            job=job,
            plan=plan,
            remote_result=result,
        )
        job.result = {**job.result, "artifacts": artifact_refs}
        session.commit()
        return job.result
    except Exception as exc:
        job.status = "failed"
        job.progress = 1.0
        job.logs = [*job.logs, "worker failed"]
        job.error = str(exc)
        session.commit()
        raise
    finally:
        session.close()
