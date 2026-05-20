"""Database-backed demo data for local workbench development."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from inflab.artifacts import sha256_text
from inflab.benchmark import build_launch_command, fake_benchmark_result, normalize_metrics
from inflab.db.models import (
    Artifact,
    BootstrapRun,
    Experiment,
    ExperimentTrial,
    JobRecord,
    Machine,
    MachineSnapshot,
    MetricsSample,
    MetricsSummary,
    ModelRecord,
    ReportRecord,
)
from inflab.reports import render_markdown_report
from inflab.schemas import (
    CommandRecord,
    CommandResult,
    FrameworkParams,
    RunSpec,
    RuntimeMode,
    StepResult,
    StepStatus,
)
from inflab.tuning import plan_candidates


def _machine_profile(host: str) -> dict[str, Any]:
    return {
        "host": host,
        "runtime_mode": "both",
        "access_mode": "demo",
        "hardware": {
            "cpu": {"model": "DemoCPU", "cores": 64},
            "memory_gb": 512,
            "gpu": [{"vendor": "nvidia", "model": "DemoA100", "memory_gb": 80, "count": 4}],
        },
        "system": {"os": "ubuntu", "version": "24.04", "kernel": "demo"},
        "container": {"docker": "available", "nvidia_container_toolkit": "available"},
        "network": {"interfaces": ["eth0"], "rdma": False},
        "storage": {"data_path": "/data", "models": "/data/models"},
    }


def _fingerprint(profile: dict[str, Any]) -> str:
    return sha256_text(str(sorted(profile.items())))


def _step_result(step_id: str, name: str, changed_files: list[str]) -> dict[str, Any]:
    command = CommandRecord(command=f"demo {step_id.lower()} detect/apply/verify")
    result = CommandResult(
        command=command,
        exit_code=0,
        stdout=f"{name} completed from demo database seed",
        stdout_uri=f"memory://demo-bootstrap/{step_id}/stdout.txt",
        stderr_uri=f"memory://demo-bootstrap/{step_id}/stderr.txt",
    )
    return StepResult(
        id=step_id,
        name=name,
        status=StepStatus.changed,
        phase_results={"detect": result, "apply": result, "verify": result},
        commands=[command],
        exit_code=0,
        stdout_uri=result.stdout_uri,
        stderr_uri=result.stderr_uri,
        changed_files=changed_files,
        snapshots={"seed": "demo"},
    ).model_dump(mode="json")


def _ensure_machine(session: Session) -> Machine:
    machine = session.scalar(select(Machine).where(Machine.name == "demo-a100-01"))
    profile = _machine_profile("10.0.0.10")
    fingerprint = _fingerprint(profile)
    if machine is None:
        machine = Machine(
            name="demo-a100-01",
            host="10.0.0.10",
            port=22,
            username="seed",
            credential_type="password",
            encrypted_credential=None,
            status="ready",
            runtime_mode="both",
            machine_profile=profile,
            fingerprint=fingerprint,
        )
        session.add(machine)
        session.flush()
    else:
        machine.status = "ready"
        machine.runtime_mode = "both"
        machine.machine_profile = profile
        machine.fingerprint = fingerprint

    snapshot = session.scalar(
        select(MachineSnapshot).where(MachineSnapshot.fingerprint == fingerprint)
    )
    if snapshot is None:
        session.add(
            MachineSnapshot(
                machine_id=machine.id,
                profile=profile,
                fingerprint=fingerprint,
                artifact_uri=f"memory://demo/snapshots/{machine.id}/{fingerprint}.json",
            )
        )
    return machine


def _ensure_model(session: Session) -> ModelRecord:
    model = session.scalar(select(ModelRecord).where(ModelRecord.name == "Demo Qwen3-32B"))
    if model is None:
        model = ModelRecord(
            name="Demo Qwen3-32B",
            source="mock",
            format="safetensors",
            sha256=sha256_text("demo-qwen3-32b"),
            cache_path="/data/models/demo-qwen3-32b",
            metadata_json={"params": "32B", "seed": "demo"},
        )
        session.add(model)
        session.flush()
    return model


def _ensure_bootstrap(session: Session, machine: Machine) -> None:
    existing = session.scalar(select(BootstrapRun).where(BootstrapRun.machine_id == machine.id))
    if existing is not None:
        return
    steps = [
        _step_result("B1", "Access Bootstrap", ["/etc/sudoers.d/inflab"]),
        _step_result("B2", "Source Bootstrap", ["/etc/apt/sources.list.d/inflab.sources"]),
        _step_result("B3", "Package Bootstrap", ["/var/lib/inflab/packages.json"]),
        _step_result("B4", "Storage Bootstrap", ["/data/models", "/data/logs"]),
        _step_result("B5", "Container Bootstrap", ["/etc/docker/daemon.json"]),
        _step_result("B6", "Baseline Capture", ["/data/logs/baseline.json"]),
        _step_result("B7", "Bare-Metal Runtime Bootstrap", ["/data/workspace/inflab-runtime"]),
    ]
    session.add(
        BootstrapRun(
            machine_id=machine.id,
            profile="full",
            status="succeeded",
            modules=[step["id"] for step in steps],
            step_results=steps,
        )
    )


def _ensure_experiment(
    session: Session,
    *,
    machine: Machine,
    model: ModelRecord,
    runtime_mode: RuntimeMode,
) -> None:
    name = f"Demo {runtime_mode.value.replace('_', ' ')} baseline"
    if session.scalar(select(Experiment).where(Experiment.name == name)) is not None:
        return

    params = FrameworkParams(
        tensor_parallel_size=4,
        gpu_memory_utilization=0.88,
        max_num_seqs=128,
    )
    run_spec = RunSpec(
        machine_id=machine.id,
        model_id=model.id,
        runtime_mode=runtime_mode,
        framework="vllm",
        framework_version="0.9.0-demo",
        framework_params=params,
        prompt_dataset="demo_prompts_v1",
        benchmark_version="inflab-bench-command-plan-v1",
    )
    launch_command = build_launch_command(run_spec)
    phases, candidates = plan_candidates(gpu_count=4, max_trials=2)
    reproducibility = {
        "machine_profile": machine.machine_profile,
        "model_hash": model.sha256,
        "runtime_mode": runtime_mode.value,
        "framework_version": run_spec.framework_version,
        "framework_params": params.model_dump(mode="json"),
        "prompt_dataset": run_spec.prompt_dataset,
        "benchmark_version": run_spec.benchmark_version,
        "launch_command": launch_command,
        "agent_phases": [phase.value for phase in phases],
        "candidate_count": len(candidates),
        "seed": "demo_database",
    }
    experiment = Experiment(
        name=name,
        machine_id=machine.id,
        model_id=model.id,
        runtime_mode=runtime_mode.value,
        framework="vllm",
        framework_version=run_spec.framework_version,
        framework_params=params.model_dump(mode="json"),
        prompt_dataset=run_spec.prompt_dataset,
        launch_command=launch_command,
        goal="max_throughput",
        status="succeeded",
        reproducibility=reproducibility,
    )
    session.add(experiment)
    session.flush()

    logs = [f"experiment {experiment.id} loaded from database seed"]
    first_metrics: dict[str, float] | None = None
    for index, candidate in enumerate(candidates, start=1):
        candidate_spec = run_spec.model_copy(update={"framework_params": candidate})
        result = fake_benchmark_result(candidate_spec)
        metrics = normalize_metrics(result)
        first_metrics = first_metrics or metrics
        trial_logs = [
            f"trial {index} started",
            f"launch: {build_launch_command(candidate_spec)}",
            f"trial {index} succeeded",
            f"tokens_per_second={metrics['tokens_per_second']}",
        ]
        trial = ExperimentTrial(
            experiment_id=experiment.id,
            trial_index=index,
            params=candidate.model_dump(mode="json"),
            launch_command=build_launch_command(candidate_spec),
            status="succeeded",
            result={
                "benchmark_result": result.model_dump(mode="json"),
                "metrics": metrics,
                "logs": trial_logs,
            },
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
        logs.extend(trial_logs)

    job = JobRecord(
        job_type="experiment",
        status="succeeded",
        progress=1.0,
        logs=[*logs, "experiment completed"],
        result={"experiment_id": experiment.id, "trial_count": len(candidates), "seed": "demo"},
    )
    session.add(job)
    session.flush()
    experiment.reproducibility = {**experiment.reproducibility, "job_id": job.id}

    markdown = render_markdown_report(
        name=experiment.name,
        runtime_mode=experiment.runtime_mode,
        framework=experiment.framework,
        framework_version=experiment.framework_version,
        prompt_dataset=experiment.prompt_dataset,
        launch_command=experiment.launch_command,
        reproducibility=experiment.reproducibility,
        metrics=first_metrics or {},
    )
    artifact = Artifact(
        kind="report",
        name=f"{experiment.name}.md",
        uri=f"memory://demo/reports/{experiment.id}/internal.md",
        sha256=sha256_text(markdown),
        size_bytes=len(markdown.encode()),
        metadata_json={"template": "internal", "seed": "demo"},
    )
    session.add(artifact)
    session.flush()
    session.add(
        ReportRecord(
            experiment_id=experiment.id,
            template="internal",
            status="succeeded",
            markdown=markdown,
            artifact_id=artifact.id,
        )
    )


def seed_demo_data(session: Session) -> dict[str, int]:
    """Create idempotent database records for a usable local demo workspace."""

    machine = _ensure_machine(session)
    model = _ensure_model(session)
    _ensure_bootstrap(session, machine)
    _ensure_experiment(session, machine=machine, model=model, runtime_mode=RuntimeMode.container)
    _ensure_experiment(session, machine=machine, model=model, runtime_mode=RuntimeMode.bare_metal)
    session.commit()
    return {
        "machines": len(session.scalars(select(Machine)).all()),
        "models": len(session.scalars(select(ModelRecord)).all()),
        "bootstrap_runs": len(session.scalars(select(BootstrapRun)).all()),
        "experiments": len(session.scalars(select(Experiment)).all()),
        "trials": len(session.scalars(select(ExperimentTrial)).all()),
        "metrics": len(session.scalars(select(MetricsSummary)).all()),
        "reports": len(session.scalars(select(ReportRecord)).all()),
    }
