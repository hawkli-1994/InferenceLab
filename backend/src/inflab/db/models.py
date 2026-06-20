"""SQLAlchemy models for the MVP control-plane database."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class Machine(Base, TimestampMixin):
    __tablename__ = "machines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, default=22)
    username: Mapped[str] = mapped_column(String(120), nullable=False)
    credential_type: Mapped[str] = mapped_column(String(40), default="password")
    encrypted_credential: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="created")
    runtime_mode: Mapped[str] = mapped_column(String(40), default="both")
    machine_profile: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    fingerprint: Mapped[str | None] = mapped_column(String(64), index=True)

    snapshots: Mapped[list[MachineSnapshot]] = relationship(
        back_populates="machine",
        cascade="all, delete-orphan",
    )


class MachineSnapshot(Base, TimestampMixin):
    __tablename__ = "machine_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id"), nullable=False)
    profile: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    artifact_uri: Mapped[str | None] = mapped_column(Text)

    machine: Mapped[Machine] = relationship(back_populates="snapshots")


class BootstrapRun(Base, TimestampMixin):
    __tablename__ = "bootstrap_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id"), nullable=False)
    profile: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="created")
    modules: Mapped[list[str]] = mapped_column(JSON, default=list)
    step_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    failure_class: Mapped[str | None] = mapped_column(String(80))
    failure_hint: Mapped[str | None] = mapped_column(Text)


class ModelRecord(Base, TimestampMixin):
    __tablename__ = "models"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    source: Mapped[str] = mapped_column(String(80), default="mock")
    format: Mapped[str] = mapped_column(String(80), default="safetensors")
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    cache_path: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class ImageRecord(Base, TimestampMixin):
    __tablename__ = "images"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    tag: Mapped[str] = mapped_column(String(120), nullable=False)
    digest: Mapped[str] = mapped_column(String(140), nullable=False)
    source: Mapped[str] = mapped_column(String(120), default="registry")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class Artifact(Base, TimestampMixin):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    uri: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AgentRuntimeSettings(Base, TimestampMixin):
    __tablename__ = "agent_runtime_settings"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default="default")
    llm_provider: Mapped[str] = mapped_column(String(40), default="disabled")
    llm_base_url: Mapped[str | None] = mapped_column(Text)
    llm_model: Mapped[str | None] = mapped_column(String(255))
    encrypted_llm_api_key: Mapped[str | None] = mapped_column(Text)
    pi_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    pi_command: Mapped[str] = mapped_column(Text, default="pi")
    pi_work_dir: Mapped[str] = mapped_column(Text, default="/data/workspace/inflab-autoresearch")
    pi_max_rounds: Mapped[int] = mapped_column(Integer, default=15)
    pi_timeout_minutes: Mapped[int] = mapped_column(Integer, default=30)


class Experiment(Base, TimestampMixin):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id"), nullable=False)
    model_id: Mapped[str] = mapped_column(ForeignKey("models.id"), nullable=False)
    runtime_mode: Mapped[str] = mapped_column(String(40), nullable=False)
    framework: Mapped[str] = mapped_column(String(80), nullable=False)
    framework_version: Mapped[str] = mapped_column(String(80), default="mock")
    framework_params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    prompt_dataset: Mapped[str] = mapped_column(String(180), nullable=False)
    launch_command: Mapped[str] = mapped_column(Text, nullable=False)
    goal: Mapped[str] = mapped_column(String(120), default="max_throughput")
    status: Mapped[str] = mapped_column(String(40), default="created")
    reproducibility: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    trials: Mapped[list[ExperimentTrial]] = relationship(
        back_populates="experiment",
        cascade="all, delete-orphan",
    )


class ExperimentTrial(Base, TimestampMixin):
    __tablename__ = "experiment_trials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"), nullable=False)
    trial_index: Mapped[int] = mapped_column(Integer, nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    launch_command: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="created")
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    failure_category: Mapped[str | None] = mapped_column(String(80))

    experiment: Mapped[Experiment] = relationship(back_populates="trials")


class MetricsSummary(Base, TimestampMixin):
    __tablename__ = "metrics_summary"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"), nullable=False)
    trial_id: Mapped[str | None] = mapped_column(ForeignKey("experiment_trials.id"))
    ttft_p50_ms: Mapped[float] = mapped_column(Float, default=0.0)
    tpot_p50_ms: Mapped[float] = mapped_column(Float, default=0.0)
    latency_p99_ms: Mapped[float] = mapped_column(Float, default=0.0)
    tokens_per_second: Mapped[float] = mapped_column(Float, default=0.0)
    requests_per_second: Mapped[float] = mapped_column(Float, default=0.0)
    failure_rate: Mapped[float] = mapped_column(Float, default=0.0)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class MetricsSample(Base):
    __tablename__ = "metrics_samples"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"), nullable=False)
    trial_id: Mapped[str | None] = mapped_column(ForeignKey("experiment_trials.id"))
    sampled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class JobRecord(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="queued")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    logs: Mapped[list[str]] = mapped_column(JSON, default=list)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)


class ReportRecord(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    experiment_id: Mapped[str] = mapped_column(ForeignKey("experiments.id"), nullable=False)
    template: Mapped[str] = mapped_column(String(80), default="internal")
    status: Mapped[str] = mapped_column(String(40), default="created")
    markdown: Mapped[str] = mapped_column(Text, default="")
    artifact_id: Mapped[str | None] = mapped_column(ForeignKey("artifacts.id"))
