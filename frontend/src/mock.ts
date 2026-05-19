import type { BootstrapRun, Experiment, Machine, MetricsSummary, ModelRecord, ReportRecord, Trial } from "./types";

const now = new Date().toISOString();

export const mockMachines: Machine[] = [
  {
    id: "machine-1",
    name: "lab-a100-01",
    host: "10.0.0.10",
    port: 22,
    username: "inflab",
    credential: "configured",
    credential_type: "password",
    status: "ready",
    runtime_mode: "both",
    fingerprint: "mock-fingerprint-a100",
    machine_profile: {
      hardware: { gpu: [{ model: "MockGPU", count: 4, memory_gb: 80 }], memory_gb: 512 },
      system: { os: "ubuntu", version: "24.04" }
    },
    created_at: now,
    updated_at: now
  }
];

export const mockModels: ModelRecord[] = [
  {
    id: "model-1",
    name: "Qwen3-32B",
    source: "mock",
    format: "safetensors",
    sha256: "mock-model-hash",
    cache_path: "/data/models/qwen3-32b",
    metadata: { params: "32B" },
    created_at: now
  }
];

export const mockBootstrapRuns: BootstrapRun[] = [
  {
    id: "bootstrap-1",
    machine_id: "machine-1",
    profile: "full",
    status: "succeeded",
    modules: ["B1", "B2", "B3", "B4", "B5", "B6", "B7"],
    step_results: [
      { id: "B1", name: "Access Bootstrap", status: "changed", changed_files: ["/etc/sudoers.d/inflab"], failure_hint: null },
      { id: "B2", name: "Source Bootstrap", status: "changed", changed_files: ["/etc/apt/sources.list"], failure_hint: null },
      { id: "B7", name: "Bare-Metal Runtime Bootstrap", status: "changed", changed_files: ["/data/workspace/inflab-venv"], failure_hint: null }
    ]
  }
];

export const mockExperiments: Experiment[] = [
  {
    id: "experiment-container",
    name: "Qwen3 container baseline",
    machine_id: "machine-1",
    model_id: "model-1",
    runtime_mode: "container",
    framework: "vllm",
    framework_version: "0.9.0-mock",
    framework_params: { tensor_parallel_size: 4, gpu_memory_utilization: 0.88 },
    prompt_dataset: "mock_prompts_v1",
    launch_command: "docker run --rm --gpus all inflab-runtime vllm serve model-1",
    goal: "max_throughput",
    status: "succeeded",
    reproducibility: { model_hash: "mock-model-hash", runtime_mode: "container" },
    created_at: now,
    updated_at: now
  },
  {
    id: "experiment-bare",
    name: "Qwen3 bare-metal baseline",
    machine_id: "machine-1",
    model_id: "model-1",
    runtime_mode: "bare_metal",
    framework: "vllm",
    framework_version: "0.9.0-mock",
    framework_params: { tensor_parallel_size: 4, gpu_memory_utilization: 0.88 },
    prompt_dataset: "mock_prompts_v1",
    launch_command: "/data/workspace/inflab-runtime/bin/vllm serve model-1",
    goal: "max_throughput",
    status: "succeeded",
    reproducibility: { model_hash: "mock-model-hash", runtime_mode: "bare_metal" },
    created_at: now,
    updated_at: now
  }
];

export const mockTrials: Trial[] = [
  {
    id: "trial-1",
    experiment_id: "experiment-container",
    trial_index: 1,
    params: { max_num_seqs: 128, gpu_memory_utilization: 0.88 },
    launch_command: "vllm serve model-1 --max-num-seqs 128",
    status: "succeeded",
    result: { throughput: { tokens_per_sec: 14784 } },
    failure_category: null,
    created_at: now
  },
  {
    id: "trial-2",
    experiment_id: "experiment-container",
    trial_index: 2,
    params: { max_num_seqs: 96, gpu_memory_utilization: 0.86 },
    launch_command: "vllm serve model-1 --max-num-seqs 96",
    status: "succeeded",
    result: { throughput: { tokens_per_sec: 13200 } },
    failure_category: null,
    created_at: now
  }
];

export const mockMetrics: MetricsSummary[] = [
  {
    id: "metrics-1",
    experiment_id: "experiment-container",
    trial_id: "trial-1",
    ttft_p50_ms: 110,
    tpot_p50_ms: 18,
    latency_p99_ms: 1480,
    tokens_per_second: 14784,
    requests_per_second: 123.2,
    failure_rate: 0,
    metrics: {}
  },
  {
    id: "metrics-2",
    experiment_id: "experiment-bare",
    trial_id: null,
    ttft_p50_ms: 118,
    tpot_p50_ms: 19,
    latency_p99_ms: 1550,
    tokens_per_second: 13920,
    requests_per_second: 116,
    failure_rate: 0,
    metrics: {}
  }
];

export const mockReports: ReportRecord[] = [
  {
    id: "report-1",
    experiment_id: "experiment-container",
    template: "internal",
    status: "succeeded",
    markdown: "# Qwen3 container baseline Performance Report",
    artifact_id: "artifact-1",
    created_at: now
  }
];
