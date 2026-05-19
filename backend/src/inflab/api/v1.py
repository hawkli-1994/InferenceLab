"""Versioned MVP API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from inflab.artifacts import distribution_plan, sha256_text
from inflab.benchmark import build_launch_command, fake_benchmark_result, normalize_metrics
from inflab.db.models import (
    Artifact,
    BootstrapRun,
    Experiment,
    ExperimentTrial,
    ImageRecord,
    JobRecord,
    Machine,
    MachineSnapshot,
    MetricsSample,
    MetricsSummary,
    ModelRecord,
    ReportRecord,
)
from inflab.db.session import get_session
from inflab.executor import ExecutionContext, FakeExecutor
from inflab.jobs import fake_queue
from inflab.plugins import registry
from inflab.reports import render_markdown_report
from inflab.schemas import (
    ArtifactCreate,
    ArtifactRead,
    BenchmarkJobCreate,
    BootstrapRequest,
    BootstrapRunRead,
    ExperimentCreate,
    ExperimentRead,
    ImageCreate,
    ImageRead,
    JobRead,
    MachineCreate,
    MachineRead,
    MachineSnapshotRead,
    MachineUpdate,
    MetricsSummaryRead,
    ModelCreate,
    ModelRead,
    Page,
    PluginInfo,
    ReportCreate,
    ReportRead,
    RuntimeMode,
    TrialRead,
)
from inflab.security import encrypt_secret, mask_secret
from inflab.steps import resolve_bootstrap_steps, run_steps
from inflab.tuning import plan_candidates

router = APIRouter(prefix="/api/v1")


def _not_found(name: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{name} not found")


def _page(rows: list[Any], total: int, limit: int, offset: int) -> Page:
    return Page(items=rows, total=total, limit=limit, offset=offset)


def _machine_fingerprint(profile: dict[str, Any]) -> str:
    return sha256_text(str(sorted(profile.items())))


def _fake_machine_profile(machine: Machine) -> dict[str, Any]:
    return {
        "host": machine.host,
        "runtime_mode": machine.runtime_mode,
        "access_mode": "permissive",
        "hardware": {
            "cpu": {"model": "MockCPU", "cores": 64},
            "memory_gb": 512,
            "gpu": [{"vendor": "nvidia", "model": "MockGPU", "memory_gb": 80, "count": 4}],
        },
        "system": {"os": "ubuntu", "version": "24.04", "kernel": "mock"},
        "container": {"docker": "dry-run", "nvidia_container_toolkit": "dry-run"},
        "network": {"interfaces": ["eth0"], "rdma": False},
        "storage": {"data_path": "/data", "models": "/data/models"},
    }


def _machine_read(machine: Machine) -> MachineRead:
    return MachineRead(
        id=machine.id,
        name=machine.name,
        host=machine.host,
        port=machine.port,
        username=machine.username,
        credential_type=machine.credential_type,
        credential=mask_secret(machine.encrypted_credential),
        status=machine.status,
        runtime_mode=RuntimeMode(machine.runtime_mode),
        machine_profile=machine.machine_profile,
        fingerprint=machine.fingerprint,
        created_at=machine.created_at,
        updated_at=machine.updated_at,
    )


def _snapshot_read(snapshot: MachineSnapshot) -> MachineSnapshotRead:
    return MachineSnapshotRead(
        id=snapshot.id,
        machine_id=snapshot.machine_id,
        profile=snapshot.profile,
        fingerprint=snapshot.fingerprint,
        artifact_uri=snapshot.artifact_uri,
        created_at=snapshot.created_at,
    )


def _bootstrap_read(run: BootstrapRun) -> BootstrapRunRead:
    return BootstrapRunRead(
        id=run.id,
        machine_id=run.machine_id,
        profile=run.profile,
        status=run.status,
        modules=run.modules,
        step_results=run.step_results,
        failure_class=run.failure_class,
        failure_hint=run.failure_hint,
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def _model_read(model: ModelRecord) -> ModelRead:
    return ModelRead(
        id=model.id,
        name=model.name,
        source=model.source,
        format=model.format,
        sha256=model.sha256,
        cache_path=model.cache_path,
        metadata=model.metadata_json,
        created_at=model.created_at,
    )


def _image_read(image: ImageRecord) -> ImageRead:
    return ImageRead(
        id=image.id,
        name=image.name,
        tag=image.tag,
        digest=image.digest,
        source=image.source,
        metadata=image.metadata_json,
        created_at=image.created_at,
    )


def _artifact_read(artifact: Artifact) -> ArtifactRead:
    return ArtifactRead(
        id=artifact.id,
        kind=artifact.kind,
        name=artifact.name,
        uri=artifact.uri,
        sha256=artifact.sha256,
        size_bytes=artifact.size_bytes,
        metadata=artifact.metadata_json,
        created_at=artifact.created_at,
    )


def _job_read(job: JobRecord) -> JobRead:
    return JobRead(
        id=job.id,
        job_type=job.job_type,
        status=job.status,
        progress=job.progress,
        logs=job.logs,
        result=job.result,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _experiment_read(experiment: Experiment) -> ExperimentRead:
    return ExperimentRead(
        id=experiment.id,
        name=experiment.name,
        machine_id=experiment.machine_id,
        model_id=experiment.model_id,
        runtime_mode=RuntimeMode(experiment.runtime_mode),
        framework=experiment.framework,
        framework_version=experiment.framework_version,
        framework_params=experiment.framework_params,
        prompt_dataset=experiment.prompt_dataset,
        launch_command=experiment.launch_command,
        goal=experiment.goal,
        status=experiment.status,
        reproducibility=experiment.reproducibility,
        created_at=experiment.created_at,
        updated_at=experiment.updated_at,
    )


def _trial_read(trial: ExperimentTrial) -> TrialRead:
    return TrialRead(
        id=trial.id,
        experiment_id=trial.experiment_id,
        trial_index=trial.trial_index,
        params=trial.params,
        launch_command=trial.launch_command,
        status=trial.status,
        result=trial.result,
        failure_category=trial.failure_category,
        created_at=trial.created_at,
    )


def _metrics_read(metrics: MetricsSummary) -> MetricsSummaryRead:
    return MetricsSummaryRead(
        id=metrics.id,
        experiment_id=metrics.experiment_id,
        trial_id=metrics.trial_id,
        ttft_p50_ms=metrics.ttft_p50_ms,
        tpot_p50_ms=metrics.tpot_p50_ms,
        latency_p99_ms=metrics.latency_p99_ms,
        tokens_per_second=metrics.tokens_per_second,
        requests_per_second=metrics.requests_per_second,
        failure_rate=metrics.failure_rate,
        metrics=metrics.metrics,
    )


def _report_read(report: ReportRecord) -> ReportRead:
    return ReportRead(
        id=report.id,
        experiment_id=report.experiment_id,
        template=report.template,
        status=report.status,
        markdown=report.markdown,
        artifact_id=report.artifact_id,
        created_at=report.created_at,
    )


@router.get("/openapi-ready", response_model=dict[str, str])
def openapi_ready() -> dict[str, str]:
    return {"status": "ok", "schema": "/openapi.json"}


@router.get("/machines", response_model=Page)
def list_machines(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> Page:
    rows = session.scalars(select(Machine).offset(offset).limit(limit)).all()
    total = len(session.scalars(select(Machine)).all())
    return _page([_machine_read(row).model_dump(mode="json") for row in rows], total, limit, offset)


@router.post("/machines", response_model=MachineRead, status_code=status.HTTP_201_CREATED)
def create_machine(payload: MachineCreate, session: Session = Depends(get_session)) -> MachineRead:
    credential_type = payload.credential.credential_type if payload.credential else "password"
    encrypted = None
    if payload.credential:
        from inflab.config import get_settings

        encrypted = encrypt_secret(payload.credential.secret, get_settings().secret_key)
    machine = Machine(
        name=payload.name,
        host=payload.host,
        port=payload.port,
        username=payload.username,
        credential_type=credential_type,
        encrypted_credential=encrypted,
        runtime_mode=payload.runtime_mode.value,
    )
    session.add(machine)
    session.commit()
    session.refresh(machine)
    return _machine_read(machine)


@router.get("/machines/{machine_id}", response_model=MachineRead)
def get_machine(machine_id: str, session: Session = Depends(get_session)) -> MachineRead:
    machine = session.get(Machine, machine_id)
    if machine is None:
        raise _not_found("machine")
    return _machine_read(machine)


@router.patch("/machines/{machine_id}", response_model=MachineRead)
def update_machine(
    machine_id: str,
    payload: MachineUpdate,
    session: Session = Depends(get_session),
) -> MachineRead:
    machine = session.get(Machine, machine_id)
    if machine is None:
        raise _not_found("machine")
    update = payload.model_dump(exclude_unset=True)
    credential = update.pop("credential", None)
    for key, value in update.items():
        if key == "runtime_mode" and value is not None:
            value = value.value
        setattr(machine, key, value)
    if credential:
        from inflab.config import get_settings

        machine.credential_type = credential["credential_type"]
        machine.encrypted_credential = encrypt_secret(
            credential["secret"], get_settings().secret_key
        )
    session.commit()
    session.refresh(machine)
    return _machine_read(machine)


@router.delete("/machines/{machine_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_machine(machine_id: str, session: Session = Depends(get_session)) -> None:
    machine = session.get(Machine, machine_id)
    if machine is None:
        raise _not_found("machine")
    session.delete(machine)
    session.commit()


@router.post("/machines/{machine_id}/probe", response_model=MachineSnapshotRead)
def probe_machine(machine_id: str, session: Session = Depends(get_session)) -> MachineSnapshotRead:
    machine = session.get(Machine, machine_id)
    if machine is None:
        raise _not_found("machine")
    profile = _fake_machine_profile(machine)
    fingerprint = _machine_fingerprint(profile)
    machine.machine_profile = profile
    machine.fingerprint = fingerprint
    machine.status = "profiled"
    snapshot = MachineSnapshot(
        machine_id=machine.id,
        profile=profile,
        fingerprint=fingerprint,
        artifact_uri=f"memory://snapshots/{machine.id}/{fingerprint}.json",
    )
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    return _snapshot_read(snapshot)


@router.get("/machines/{machine_id}/snapshots", response_model=list[MachineSnapshotRead])
def list_machine_snapshots(
    machine_id: str,
    session: Session = Depends(get_session),
) -> list[MachineSnapshotRead]:
    rows = session.scalars(
        select(MachineSnapshot).where(MachineSnapshot.machine_id == machine_id)
    ).all()
    return [_snapshot_read(row) for row in rows]


@router.post("/machines/{machine_id}/bootstrap", response_model=BootstrapRunRead)
async def bootstrap_machine(
    machine_id: str,
    payload: BootstrapRequest,
    session: Session = Depends(get_session),
) -> BootstrapRunRead:
    machine = session.get(Machine, machine_id)
    if machine is None:
        raise _not_found("machine")
    steps = resolve_bootstrap_steps(payload.profile.value, payload.modules)
    ctx = ExecutionContext(machine_id=machine_id, dry_run=payload.dry_run)
    results = await run_steps(steps, ctx, FakeExecutor())
    run = BootstrapRun(
        machine_id=machine_id,
        profile=payload.profile.value,
        status="succeeded",
        modules=[step.id for step in steps],
        step_results=[result.model_dump(mode="json") for result in results],
    )
    machine.status = "ready"
    session.add(run)
    session.commit()
    session.refresh(run)
    return _bootstrap_read(run)


@router.get("/bootstrap-runs", response_model=list[BootstrapRunRead])
def list_bootstrap_runs(session: Session = Depends(get_session)) -> list[BootstrapRunRead]:
    return [_bootstrap_read(row) for row in session.scalars(select(BootstrapRun)).all()]


@router.get("/bootstrap-runs/{run_id}", response_model=BootstrapRunRead)
def get_bootstrap_run(run_id: str, session: Session = Depends(get_session)) -> BootstrapRunRead:
    run = session.get(BootstrapRun, run_id)
    if run is None:
        raise _not_found("bootstrap run")
    return _bootstrap_read(run)


@router.post("/bootstrap-runs/{run_id}/rerun-module/{module_id}", response_model=BootstrapRunRead)
async def rerun_bootstrap_module(
    run_id: str,
    module_id: str,
    session: Session = Depends(get_session),
) -> BootstrapRunRead:
    run = session.get(BootstrapRun, run_id)
    if run is None:
        raise _not_found("bootstrap run")
    results = await run_steps(
        resolve_bootstrap_steps("custom", [module_id]),
        ExecutionContext(machine_id=run.machine_id, dry_run=True),
        FakeExecutor(),
    )
    run.status = "succeeded"
    run.modules = sorted({*run.modules, module_id})
    run.step_results = [
        *run.step_results,
        *[result.model_dump(mode="json") for result in results],
    ]
    session.commit()
    session.refresh(run)
    return _bootstrap_read(run)


@router.post("/models", response_model=ModelRead, status_code=status.HTTP_201_CREATED)
def create_model(payload: ModelCreate, session: Session = Depends(get_session)) -> ModelRead:
    model = ModelRecord(
        name=payload.name,
        source=payload.source,
        format=payload.format,
        sha256=payload.sha256 or sha256_text(f"{payload.name}:{payload.cache_path}"),
        cache_path=payload.cache_path,
        metadata_json=payload.metadata,
    )
    session.add(model)
    session.commit()
    session.refresh(model)
    return _model_read(model)


@router.get("/models", response_model=list[ModelRead])
def list_models(session: Session = Depends(get_session)) -> list[ModelRead]:
    return [_model_read(row) for row in session.scalars(select(ModelRecord)).all()]


@router.get("/models/{model_id}", response_model=ModelRead)
def get_model(model_id: str, session: Session = Depends(get_session)) -> ModelRead:
    model = session.get(ModelRecord, model_id)
    if model is None:
        raise _not_found("model")
    return _model_read(model)


@router.post("/models/{model_id}/verify", response_model=dict[str, bool])
def verify_model(model_id: str, session: Session = Depends(get_session)) -> dict[str, bool]:
    model = session.get(ModelRecord, model_id)
    if model is None:
        raise _not_found("model")
    return {"verified": registry.models["sha256"].verify(model.cache_path, model.sha256)}


@router.post("/models/{model_id}/distribution-plan", response_model=dict[str, str])
def model_distribution_plan(
    model_id: str, session: Session = Depends(get_session)
) -> dict[str, str]:
    model = session.get(ModelRecord, model_id)
    if model is None:
        raise _not_found("model")
    return distribution_plan(model.source, model.cache_path)


@router.post("/images", response_model=ImageRead, status_code=status.HTTP_201_CREATED)
def create_image(payload: ImageCreate, session: Session = Depends(get_session)) -> ImageRead:
    image = ImageRecord(
        name=payload.name,
        tag=payload.tag,
        digest=payload.digest,
        source=payload.source,
        metadata_json=payload.metadata,
    )
    session.add(image)
    session.commit()
    session.refresh(image)
    return _image_read(image)


@router.get("/images", response_model=list[ImageRead])
def list_images(session: Session = Depends(get_session)) -> list[ImageRead]:
    return [_image_read(row) for row in session.scalars(select(ImageRecord)).all()]


@router.post("/artifacts", response_model=ArtifactRead, status_code=status.HTTP_201_CREATED)
def create_artifact(
    payload: ArtifactCreate, session: Session = Depends(get_session)
) -> ArtifactRead:
    artifact = Artifact(
        kind=payload.kind,
        name=payload.name,
        uri=payload.uri,
        sha256=payload.sha256,
        size_bytes=payload.size_bytes,
        metadata_json=payload.metadata,
    )
    session.add(artifact)
    session.commit()
    session.refresh(artifact)
    return _artifact_read(artifact)


@router.get("/artifacts", response_model=list[ArtifactRead])
def list_artifacts(session: Session = Depends(get_session)) -> list[ArtifactRead]:
    return [_artifact_read(row) for row in session.scalars(select(Artifact)).all()]


@router.post("/benchmarks/jobs", response_model=JobRead, status_code=status.HTTP_201_CREATED)
def create_benchmark_job(
    payload: BenchmarkJobCreate,
    session: Session = Depends(get_session),
) -> JobRead:
    if session.get(Machine, payload.run_spec.machine_id) is None:
        raise _not_found("machine")
    if session.get(ModelRecord, payload.run_spec.model_id) is None:
        raise _not_found("model")

    def handler() -> dict[str, Any]:
        result = fake_benchmark_result(payload.run_spec)
        return {
            "launch_command": build_launch_command(payload.run_spec),
            "benchmark_result": result.model_dump(mode="json"),
            "metrics": normalize_metrics(result),
        }

    return _job_read(fake_queue.enqueue(session, "benchmark", handler))


@router.get("/jobs", response_model=list[JobRead])
def list_jobs(session: Session = Depends(get_session)) -> list[JobRead]:
    return [_job_read(row) for row in session.scalars(select(JobRecord)).all()]


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: str, session: Session = Depends(get_session)) -> JobRead:
    job = session.get(JobRecord, job_id)
    if job is None:
        raise _not_found("job")
    return _job_read(job)


@router.get("/jobs/{job_id}/logs", response_model=dict[str, list[str]])
def get_job_logs(job_id: str, session: Session = Depends(get_session)) -> dict[str, list[str]]:
    job = session.get(JobRecord, job_id)
    if job is None:
        raise _not_found("job")
    return {"logs": job.logs}


@router.get("/jobs/{job_id}/progress", response_model=dict[str, float | str])
def get_job_progress(
    job_id: str, session: Session = Depends(get_session)
) -> dict[str, float | str]:
    job = session.get(JobRecord, job_id)
    if job is None:
        raise _not_found("job")
    return {"status": job.status, "progress": job.progress}


@router.post("/experiments", response_model=ExperimentRead, status_code=status.HTTP_201_CREATED)
def create_experiment(
    payload: ExperimentCreate, session: Session = Depends(get_session)
) -> ExperimentRead:
    machine = session.get(Machine, payload.run_spec.machine_id)
    model = session.get(ModelRecord, payload.run_spec.model_id)
    if machine is None:
        raise _not_found("machine")
    if model is None:
        raise _not_found("model")
    launch_command = build_launch_command(payload.run_spec)
    reproducibility = {
        "machine_profile": machine.machine_profile,
        "model_hash": model.sha256,
        "runtime_mode": payload.run_spec.runtime_mode.value,
        "framework_version": payload.run_spec.framework_version,
        "framework_params": payload.run_spec.framework_params.model_dump(mode="json"),
        "prompt_dataset": payload.run_spec.prompt_dataset,
        "launch_command": launch_command,
    }
    experiment = Experiment(
        name=payload.name,
        machine_id=machine.id,
        model_id=model.id,
        runtime_mode=payload.run_spec.runtime_mode.value,
        framework=payload.run_spec.framework,
        framework_version=payload.run_spec.framework_version,
        framework_params=payload.run_spec.framework_params.model_dump(mode="json"),
        prompt_dataset=payload.run_spec.prompt_dataset,
        launch_command=launch_command,
        goal=payload.goal,
        status="succeeded",
        reproducibility=reproducibility,
    )
    session.add(experiment)
    session.flush()

    _, candidates = plan_candidates(max_trials=int(payload.budget.get("max_trials", 2)))
    for index, candidate in enumerate(candidates, start=1):
        candidate_spec = payload.run_spec.model_copy(update={"framework_params": candidate})
        result = fake_benchmark_result(candidate_spec)
        metrics = normalize_metrics(result)
        trial = ExperimentTrial(
            experiment_id=experiment.id,
            trial_index=index,
            params=candidate.model_dump(mode="json"),
            launch_command=build_launch_command(candidate_spec),
            status="succeeded",
            result=result.model_dump(mode="json"),
        )
        session.add(trial)
        session.flush()
        session.add(
            MetricsSummary(
                experiment_id=experiment.id,
                trial_id=trial.id,
                metrics=metrics,
                **metrics,
            )
        )
        session.add(
            MetricsSample(
                experiment_id=experiment.id,
                trial_id=trial.id,
                metrics={
                    "gpu_utilization": 0.88,
                    "tokens_per_second": metrics["tokens_per_second"],
                },
            )
        )
    session.commit()
    session.refresh(experiment)
    return _experiment_read(experiment)


@router.get("/experiments", response_model=list[ExperimentRead])
def list_experiments(session: Session = Depends(get_session)) -> list[ExperimentRead]:
    return [_experiment_read(row) for row in session.scalars(select(Experiment)).all()]


@router.get("/experiments/{experiment_id}", response_model=ExperimentRead)
def get_experiment(experiment_id: str, session: Session = Depends(get_session)) -> ExperimentRead:
    experiment = session.get(Experiment, experiment_id)
    if experiment is None:
        raise _not_found("experiment")
    return _experiment_read(experiment)


@router.post("/experiments/{experiment_id}/cancel", response_model=ExperimentRead)
def cancel_experiment(
    experiment_id: str, session: Session = Depends(get_session)
) -> ExperimentRead:
    experiment = session.get(Experiment, experiment_id)
    if experiment is None:
        raise _not_found("experiment")
    experiment.status = "canceled"
    session.commit()
    session.refresh(experiment)
    return _experiment_read(experiment)


@router.post("/experiments/{experiment_id}/copy", response_model=ExperimentRead)
def copy_experiment(experiment_id: str, session: Session = Depends(get_session)) -> ExperimentRead:
    experiment = session.get(Experiment, experiment_id)
    if experiment is None:
        raise _not_found("experiment")
    clone = Experiment(
        name=f"{experiment.name} copy",
        machine_id=experiment.machine_id,
        model_id=experiment.model_id,
        runtime_mode=experiment.runtime_mode,
        framework=experiment.framework,
        framework_version=experiment.framework_version,
        framework_params=experiment.framework_params,
        prompt_dataset=experiment.prompt_dataset,
        launch_command=experiment.launch_command,
        goal=experiment.goal,
        status="created",
        reproducibility=experiment.reproducibility,
    )
    session.add(clone)
    session.commit()
    session.refresh(clone)
    return _experiment_read(clone)


@router.get("/experiments/{experiment_id}/trials", response_model=list[TrialRead])
def list_trials(experiment_id: str, session: Session = Depends(get_session)) -> list[TrialRead]:
    rows = session.scalars(
        select(ExperimentTrial).where(ExperimentTrial.experiment_id == experiment_id)
    ).all()
    return [_trial_read(row) for row in rows]


@router.get("/experiments/{experiment_id}/metrics", response_model=list[MetricsSummaryRead])
def list_metrics(
    experiment_id: str, session: Session = Depends(get_session)
) -> list[MetricsSummaryRead]:
    rows = session.scalars(
        select(MetricsSummary).where(MetricsSummary.experiment_id == experiment_id)
    ).all()
    return [_metrics_read(row) for row in rows]


@router.get("/experiments/{experiment_id}/chart-data", response_model=dict[str, Any])
def experiment_chart_data(
    experiment_id: str,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    rows = session.scalars(
        select(MetricsSummary).where(MetricsSummary.experiment_id == experiment_id)
    ).all()
    return {
        "experiment_id": experiment_id,
        "series": [
            {
                "trial_id": row.trial_id,
                "tokens_per_second": row.tokens_per_second,
                "latency_p99_ms": row.latency_p99_ms,
                "ttft_p50_ms": row.ttft_p50_ms,
            }
            for row in rows
        ],
    }


@router.get("/experiments/compare/{left_id}/{right_id}", response_model=dict[str, Any])
def compare_experiments(
    left_id: str,
    right_id: str,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    left = session.get(Experiment, left_id)
    right = session.get(Experiment, right_id)
    if left is None or right is None:
        raise _not_found("experiment")
    return {
        "left": _experiment_read(left).model_dump(mode="json"),
        "right": _experiment_read(right).model_dump(mode="json"),
        "runtime_delta": f"{left.runtime_mode}_vs_{right.runtime_mode}",
    }


@router.post("/experiments/{experiment_id}/reports", response_model=ReportRead)
def generate_report(
    experiment_id: str,
    payload: ReportCreate,
    session: Session = Depends(get_session),
) -> ReportRead:
    experiment = session.get(Experiment, experiment_id)
    if experiment is None:
        raise _not_found("experiment")
    metrics = session.scalar(
        select(MetricsSummary).where(MetricsSummary.experiment_id == experiment_id)
    )
    metric_values = metrics.metrics if metrics else {}
    markdown = render_markdown_report(
        name=experiment.name,
        runtime_mode=experiment.runtime_mode,
        framework=experiment.framework,
        framework_version=experiment.framework_version,
        prompt_dataset=experiment.prompt_dataset,
        launch_command=experiment.launch_command,
        reproducibility=experiment.reproducibility,
        metrics=metric_values,
    )
    artifact = Artifact(
        kind="report",
        name=f"{experiment.name}.md",
        uri=f"memory://reports/{experiment.id}/{payload.template}.md",
        sha256=sha256_text(markdown),
        size_bytes=len(markdown.encode()),
        metadata_json={
            "template": payload.template,
            "formats": ["markdown", "pdf_stub", "docx_stub"],
        },
    )
    session.add(artifact)
    session.flush()
    report = ReportRecord(
        experiment_id=experiment.id,
        template=payload.template,
        status="succeeded",
        markdown=markdown,
        artifact_id=artifact.id,
    )
    session.add(report)
    session.commit()
    session.refresh(report)
    return _report_read(report)


@router.get("/reports/{report_id}", response_model=ReportRead)
def get_report(report_id: str, session: Session = Depends(get_session)) -> ReportRead:
    report = session.get(ReportRecord, report_id)
    if report is None:
        raise _not_found("report")
    return _report_read(report)


@router.get("/reports/{report_id}/download", response_model=dict[str, str])
def download_report(
    report_id: str,
    format: str = Query(default="markdown", pattern="^(markdown|pdf|docx)$"),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    report = session.get(ReportRecord, report_id)
    if report is None:
        raise _not_found("report")
    extension = {"markdown": "md", "pdf": "pdf", "docx": "docx"}[format]
    return {
        "format": format,
        "uri": f"memory://reports/{report.experiment_id}/{report.id}.{extension}",
    }


@router.get("/plugins", response_model=list[PluginInfo])
def list_plugins() -> list[PluginInfo]:
    return registry.list_plugins()
