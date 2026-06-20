"""Pydantic API contracts for the MVP backend."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class RuntimeMode(StrEnum):
    container = "container"
    bare_metal = "bare_metal"
    both = "both"


class ExperimentMode(StrEnum):
    standard = "standard"
    intelligent = "intelligent"


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    canceled = "canceled"


class BootstrapProfile(StrEnum):
    minimal = "minimal"
    standard_container = "standard_container"
    standard_bare_metal = "standard_bare_metal"
    full = "full"
    custom = "custom"


class BenchmarkKind(StrEnum):
    serve = "serve"
    throughput = "throughput"


class StepStatus(StrEnum):
    skipped = "skipped"
    unchanged = "unchanged"
    changed = "changed"
    failed = "failed"


class LLMProviderName(StrEnum):
    disabled = "disabled"
    openai_compatible = "openai_compatible"
    anthropic = "anthropic"


class ValidationStatus(StrEnum):
    passed = "passed"
    warning = "warning"
    failed = "failed"


class Page(BaseModel):
    items: list[Any]
    total: int
    limit: int = 50
    offset: int = 0


class SSHCredential(BaseModel):
    credential_type: Literal["password", "private_key"] = "password"
    secret: str = Field(min_length=1)


class MachineCreate(BaseModel):
    name: str
    host: str
    port: int = Field(default=22, ge=1, le=65535)
    username: str
    credential: SSHCredential | None = None
    runtime_mode: RuntimeMode = RuntimeMode.both


class MachineUpdate(BaseModel):
    name: str | None = None
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = None
    credential: SSHCredential | None = None
    runtime_mode: RuntimeMode | None = None
    status: str | None = None


class MachineRead(BaseModel):
    id: str
    name: str
    host: str
    port: int
    username: str
    credential_type: str
    credential: str
    status: str
    runtime_mode: RuntimeMode
    machine_profile: dict[str, Any]
    fingerprint: str | None
    created_at: datetime
    updated_at: datetime


class MachineSnapshotRead(BaseModel):
    id: str
    machine_id: str
    profile: dict[str, Any]
    fingerprint: str
    artifact_uri: str | None
    created_at: datetime


class CommandRecord(BaseModel):
    command: str
    cwd: str | None = None
    env: dict[str, str] = Field(default_factory=dict)
    sudo: bool = False


class CommandResult(BaseModel):
    command: CommandRecord
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    stdout_uri: str | None = None
    stderr_uri: str | None = None


class StepResult(BaseModel):
    id: str
    name: str
    status: StepStatus
    phase_results: dict[str, CommandResult]
    commands: list[CommandRecord]
    exit_code: int
    stdout_uri: str | None = None
    stderr_uri: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    snapshots: dict[str, Any] = Field(default_factory=dict)
    failure_hint: str | None = None


class BootstrapRequest(BaseModel):
    profile: BootstrapProfile = BootstrapProfile.full
    modules: list[str] | None = None
    dry_run: bool = True
    manual_environment: bool = False
    manual_environment_note: str | None = Field(default=None, max_length=500)


class BootstrapRunRead(BaseModel):
    id: str
    machine_id: str
    profile: BootstrapProfile
    status: JobStatus
    modules: list[str]
    step_results: list[StepResult]
    failure_class: str | None
    failure_hint: str | None
    created_at: datetime
    updated_at: datetime


class ModelCreate(BaseModel):
    name: str
    source: Literal["mock", "rsync", "nfs", "minio", "huggingface", "modelscope"] = "mock"
    format: str = "safetensors"
    sha256: str | None = None
    cache_path: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelRead(BaseModel):
    id: str
    name: str
    source: str
    format: str
    sha256: str
    cache_path: str
    metadata: dict[str, Any]
    created_at: datetime


class ModelDistributeRequest(BaseModel):
    machine_id: str
    target_path: str | None = None
    dry_run: bool = True


class ModelDistributeRead(BaseModel):
    model_id: str
    machine_id: str
    source: str
    target_path: str
    result: dict[str, Any]


class ImageCreate(BaseModel):
    name: str
    tag: str
    digest: str
    source: str = "registry"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ImageRead(BaseModel):
    id: str
    name: str
    tag: str
    digest: str
    source: str
    metadata: dict[str, Any]
    created_at: datetime


class ArtifactCreate(BaseModel):
    kind: Literal["log", "report", "snapshot", "metrics", "model", "image"]
    name: str
    uri: str
    sha256: str | None = None
    size_bytes: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactRead(BaseModel):
    id: str
    kind: str
    name: str
    uri: str
    sha256: str | None
    size_bytes: int
    metadata: dict[str, Any]
    created_at: datetime


class ArtifactUploadText(BaseModel):
    kind: Literal["log", "report", "snapshot", "metrics"]
    name: str
    content: str
    content_type: str = "text/plain"
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentSettingsLLMRead(BaseModel):
    provider: LLMProviderName
    base_url: str | None
    model: str | None
    api_key_configured: bool


class AgentSettingsPiRead(BaseModel):
    enabled: bool
    command: str
    work_dir: str
    max_rounds: int
    timeout_minutes: int


class AgentSettingsRead(BaseModel):
    llm: AgentSettingsLLMRead
    pi: AgentSettingsPiRead
    pi_executor_plan: dict[str, Any]
    worker_prompt: str
    standard_mode_note: str


class AgentSettingsLLMUpdate(BaseModel):
    provider: LLMProviderName = LLMProviderName.disabled
    base_url: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=255)
    api_key: str | None = Field(default=None, max_length=4096)
    clear_api_key: bool = False


class AgentSettingsPiUpdate(BaseModel):
    enabled: bool = True
    command: str = Field(default="pi", min_length=1, max_length=500)
    work_dir: str = Field(
        default="/data/workspace/inflab-autoresearch",
        min_length=1,
        max_length=500,
    )
    max_rounds: int = Field(default=15, ge=1, le=200)
    timeout_minutes: int = Field(default=30, ge=1, le=1440)


class AgentSettingsUpdate(BaseModel):
    llm: AgentSettingsLLMUpdate = Field(default_factory=AgentSettingsLLMUpdate)
    pi: AgentSettingsPiUpdate = Field(default_factory=AgentSettingsPiUpdate)


class AgentSettingsValidationCheck(BaseModel):
    key: str
    status: ValidationStatus
    message: str


class AgentSettingsValidationRead(BaseModel):
    status: Literal["valid", "invalid"]
    checks: list[AgentSettingsValidationCheck]


class FrameworkParams(BaseModel):
    tensor_parallel_size: int = Field(default=1, ge=1)
    pipeline_parallel_size: int = Field(default=1, ge=1)
    gpu_memory_utilization: float = Field(default=0.9, gt=0, le=1)
    max_model_len: int = Field(default=4096, ge=1)
    max_num_seqs: int = Field(default=128, ge=1)
    max_num_batched_tokens: int = Field(default=8192, ge=1)
    dtype: str = "bfloat16"
    quantization: str | None = None
    enable_chunked_prefill: bool = True
    enable_prefix_caching: bool = True


class RunSpec(BaseModel):
    machine_id: str
    model_id: str
    runtime_mode: RuntimeMode
    framework: Literal["vllm", "sglang"]
    framework_version: str = "mock"
    framework_params: FrameworkParams = Field(default_factory=FrameworkParams)
    prompt_dataset: str = "mock_prompts_v1"
    benchmark_version: str = "inflab-bench-mock-v1"

    @model_validator(mode="after")
    def runtime_must_be_single_mode(self) -> RunSpec:
        if self.runtime_mode == RuntimeMode.both:
            raise ValueError("run specs must choose container or bare_metal")
        return self


class BenchmarkResult(BaseModel):
    request_count: int
    success_count: int
    failure_count: int
    latency_ms: dict[str, float]
    ttft_ms: dict[str, float]
    tpot_ms: dict[str, float]
    throughput: dict[str, float]
    gpu: dict[str, Any] = Field(default_factory=dict)
    power: dict[str, Any] = Field(default_factory=dict)
    failures: list[dict[str, Any]] = Field(default_factory=list)


class BenchmarkPlanCreate(BaseModel):
    run_spec: RunSpec
    kind: BenchmarkKind = BenchmarkKind.serve
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    dataset_name: str = "random"
    input_len: int = Field(default=1024, ge=1)
    output_len: int = Field(default=256, ge=1)
    num_prompts: int = Field(default=128, ge=1)
    request_rate: float | None = Field(default=None, gt=0)
    result_dir: str = "/data/logs/inflab-bench"
    result_filename: str = "vllm-bench-result.json"


class BenchmarkJobCreate(BaseModel):
    run_spec: RunSpec
    execution_mode: Literal["fake", "remote_rq", "remote_inline"] = "fake"
    benchmark: BenchmarkPlanCreate | None = None


class BenchmarkCommandPlan(BaseModel):
    framework: str
    kind: BenchmarkKind
    serve_command: str | None
    bench_command: str
    result_path: str
    parser: str
    notes: list[str]


class JobRead(BaseModel):
    id: str
    job_type: str
    status: JobStatus
    progress: float
    logs: list[str]
    result: dict[str, Any]
    error: str | None
    created_at: datetime
    updated_at: datetime


class ExperimentCreate(BaseModel):
    name: str
    run_spec: RunSpec
    mode: ExperimentMode = ExperimentMode.standard
    goal: str = "max_throughput"
    budget: dict[str, Any] = Field(default_factory=lambda: {"max_trials": 2})


class ExperimentPlanRequest(BaseModel):
    run_spec: RunSpec
    mode: ExperimentMode = ExperimentMode.standard
    budget: dict[str, Any] = Field(default_factory=lambda: {"max_trials": 2})


class ExperimentCandidateRead(BaseModel):
    trial_index: int
    params: dict[str, Any]
    launch_command: str
    validation: str


class ExperimentPlanRead(BaseModel):
    mode: ExperimentMode
    phases: list[str]
    candidates: list[ExperimentCandidateRead]
    trial_count: int
    notes: list[str]


class ExperimentRead(BaseModel):
    id: str
    name: str
    mode: ExperimentMode
    machine_id: str
    model_id: str
    runtime_mode: RuntimeMode
    framework: str
    framework_version: str
    framework_params: dict[str, Any]
    prompt_dataset: str
    launch_command: str
    goal: str
    status: JobStatus
    reproducibility: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class TrialRead(BaseModel):
    id: str
    experiment_id: str
    trial_index: int
    params: dict[str, Any]
    launch_command: str
    status: JobStatus
    result: dict[str, Any]
    failure_category: str | None
    created_at: datetime


class MetricsSummaryRead(BaseModel):
    id: str
    experiment_id: str
    trial_id: str | None
    ttft_p50_ms: float
    tpot_p50_ms: float
    latency_p99_ms: float
    tokens_per_second: float
    requests_per_second: float
    failure_rate: float
    metrics: dict[str, Any]


class ExperimentRunLogRead(BaseModel):
    experiment_id: str
    lines: list[str]


class ReportCreate(BaseModel):
    template: Literal["internal", "customer", "whitepaper"] = "internal"


class ReportRead(BaseModel):
    id: str
    experiment_id: str
    template: str
    status: JobStatus
    markdown: str
    artifact_id: str | None
    created_at: datetime


class PluginInfo(BaseModel):
    kind: str
    name: str
    supported_runtime_modes: list[RuntimeMode]
    capabilities: list[str]
