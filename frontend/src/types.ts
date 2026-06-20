export type RuntimeMode = "container" | "bare_metal" | "both";
export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "canceled";
export type ExecutionMode = "fake" | "remote_inline" | "remote_rq";
export type BenchmarkKind = "serve" | "throughput";
export type ExperimentMode = "standard" | "intelligent";

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

export interface BootstrapPayload {
  profile: string;
  dry_run: boolean;
}

export interface MachineSnapshot {
  id: string;
  machine_id: string;
  profile: Record<string, unknown>;
  fingerprint: string;
  artifact_uri: string | null;
  created_at: string;
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
  source: ModelSource;
  format: string;
  cache_path: string;
  sha256?: string;
  metadata?: Record<string, unknown>;
}

export type ModelSource = "mock" | "rsync" | "nfs" | "minio" | "huggingface" | "modelscope";

export interface ModelDistributePayload {
  machine_id: string;
  target_path?: string;
  dry_run: boolean;
}

export interface ModelDistributeResult {
  model_id: string;
  machine_id: string;
  source: string;
  target_path: string;
  result: Record<string, unknown>;
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

export interface BenchmarkPlanPayload {
  run_spec: RunSpec;
  kind: BenchmarkKind;
  host?: string;
  port?: number;
  dataset_name?: string;
  input_len?: number;
  output_len?: number;
  num_prompts?: number;
  request_rate?: number;
  result_dir?: string;
  result_filename?: string;
}

export interface BenchmarkJobPayload {
  run_spec: RunSpec;
  execution_mode: ExecutionMode;
  benchmark?: BenchmarkPlanPayload;
}

export interface JobRecord {
  id: string;
  job_type: string;
  status: JobStatus;
  progress: number;
  logs: string[];
  result: Record<string, unknown>;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExperimentCreatePayload {
  name: string;
  mode: ExperimentMode;
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
  mode: ExperimentMode;
  phases: string[];
  candidates: ExperimentCandidate[];
  trial_count: number;
  notes: string[];
}

export interface Experiment {
  id: string;
  name: string;
  mode: ExperimentMode;
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

export interface ReportDownload {
  format: string;
  uri: string;
  presigned_url?: string;
}

export interface ArtifactRecord {
  id: string;
  kind: string;
  name: string;
  uri: string;
  sha256: string | null;
  size_bytes: number;
  metadata: Record<string, unknown>;
  created_at: string;
}
