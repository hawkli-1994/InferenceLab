export type RuntimeMode = "container" | "bare_metal" | "both";
export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "canceled";

export interface Machine {
  id: string;
  name: string;
  host: string;
  port: number;
  username: string;
  credential: string;
  credential_type: string;
  status: string;
  runtime_mode: RuntimeMode;
  machine_profile: Record<string, unknown>;
  fingerprint: string | null;
  created_at: string;
  updated_at: string;
}

export interface BootstrapRun {
  id: string;
  machine_id: string;
  profile: string;
  status: JobStatus;
  modules: string[];
  step_results: Array<{
    id: string;
    name: string;
    status: string;
    changed_files: string[];
    failure_hint: string | null;
  }>;
}

export interface ModelRecord {
  id: string;
  name: string;
  source: string;
  format: string;
  sha256: string;
  cache_path: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface ModelCreatePayload {
  name: string;
  source: "mock" | "rsync" | "nfs" | "minio" | "huggingface" | "modelscope";
  format: string;
  cache_path: string;
  sha256?: string;
  metadata?: Record<string, unknown>;
}

export interface MachineCreatePayload {
  name: string;
  host: string;
  port: number;
  username: string;
  runtime_mode: RuntimeMode;
  credential?: {
    credential_type: "password" | "private_key";
    secret: string;
  };
}

export interface FrameworkParams {
  tensor_parallel_size?: number;
  pipeline_parallel_size?: number;
  gpu_memory_utilization?: number;
  max_model_len?: number;
  max_num_seqs?: number;
  max_num_batched_tokens?: number;
  dtype?: string;
  quantization?: string | null;
  enable_chunked_prefill?: boolean;
  enable_prefix_caching?: boolean;
}

export interface RunSpec {
  machine_id: string;
  model_id: string;
  runtime_mode: Exclude<RuntimeMode, "both">;
  framework: "vllm" | "sglang";
  framework_version?: string;
  framework_params?: FrameworkParams;
  prompt_dataset?: string;
  benchmark_version?: string;
}

export interface ExperimentCreatePayload {
  name: string;
  run_spec: RunSpec;
  goal: string;
  budget: {
    max_trials: number;
  };
}

export interface ExperimentCandidate {
  trial_index: number;
  params: Record<string, unknown>;
  launch_command: string;
  validation: string;
}

export interface ExperimentPlan {
  phases: string[];
  candidates: ExperimentCandidate[];
  trial_count: number;
  notes: string[];
}

export interface Experiment {
  id: string;
  name: string;
  machine_id: string;
  model_id: string;
  runtime_mode: RuntimeMode;
  framework: string;
  framework_version: string;
  framework_params: Record<string, unknown>;
  prompt_dataset: string;
  launch_command: string;
  goal: string;
  status: JobStatus;
  reproducibility: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Trial {
  id: string;
  experiment_id: string;
  trial_index: number;
  params: Record<string, unknown>;
  launch_command: string;
  status: JobStatus;
  result: Record<string, unknown>;
  failure_category: string | null;
  created_at: string;
}

export interface ExperimentRunLog {
  experiment_id: string;
  lines: string[];
}

export interface MetricsSummary {
  id: string;
  experiment_id: string;
  trial_id: string | null;
  ttft_p50_ms: number;
  tpot_p50_ms: number;
  latency_p99_ms: number;
  tokens_per_second: number;
  requests_per_second: number;
  failure_rate: number;
  metrics: Record<string, unknown>;
}

export interface ReportRecord {
  id: string;
  experiment_id: string;
  template: string;
  status: JobStatus;
  markdown: string;
  artifact_id: string | null;
  created_at: string;
}
