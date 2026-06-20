import type {
  ArtifactRecord,
  BootstrapPayload,
  BenchmarkJobPayload,
  BootstrapRun,
  Experiment,
  ExperimentCreatePayload,
  ExperimentPlan,
  ExperimentRunLog,
  JobRecord,
  Machine,
  MachineCreatePayload,
  MachineSnapshot,
  MetricsSummary,
  ModelDistributePayload,
  ModelDistributeResult,
  ModelCreatePayload,
  ModelRecord,
  ReportDownload,
  ReportRecord,
  Trial
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "/api/v1";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  const data = await response.json();
  if (data && Array.isArray(data.items)) {
    return data.items as T;
  }
  return data as T;
}

async function sendJson<T>(path: string, body: unknown = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export const api = {
  machines: () => getJson<Machine[]>("/machines"),
  models: () => getJson<ModelRecord[]>("/models"),
  bootstrapRuns: () => getJson<BootstrapRun[]>("/bootstrap-runs"),
  experiments: () => getJson<Experiment[]>("/experiments"),
  trials: (experimentId: string) => getJson<Trial[]>(`/experiments/${experimentId}/trials`),
  metrics: (experimentId: string) => getJson<MetricsSummary[]>(`/experiments/${experimentId}/metrics`),
  reports: (experimentId?: string) =>
    getJson<ReportRecord[]>(experimentId ? `/reports?experiment_id=${experimentId}` : "/reports"),
  seedDemoData: () => sendJson<Record<string, number>>("/dev/seed-demo-data"),
  createMachine: (payload: MachineCreatePayload) => sendJson<Machine>("/machines", payload),
  probeMachine: (machineId: string, dryRun = true) =>
    sendJson<MachineSnapshot>(`/machines/${machineId}/probe?dry_run=${dryRun}`, {}),
  bootstrapMachine: (machineId: string, payload: BootstrapPayload) =>
    sendJson<BootstrapRun>(`/machines/${machineId}/bootstrap`, payload),
  confirmManualEnvironment: (machineId: string, note?: string) =>
    sendJson<BootstrapRun>(`/machines/${machineId}/bootstrap`, {
      profile: "full",
      dry_run: true,
      manual_environment: true,
      manual_environment_note: note
    }),
  createModel: (payload: ModelCreatePayload) => sendJson<ModelRecord>("/models", payload),
  distributeModel: (modelId: string, payload: ModelDistributePayload) =>
    sendJson<ModelDistributeResult>(`/models/${modelId}/distribute`, payload),
  planExperiment: (payload: ExperimentCreatePayload) =>
    sendJson<ExperimentPlan>("/experiments/plan", {
      run_spec: payload.run_spec,
      mode: payload.mode,
      budget: payload.budget
    }),
  createExperiment: (payload: ExperimentCreatePayload) =>
    sendJson<Experiment>("/experiments", payload),
  createBenchmarkJob: (payload: BenchmarkJobPayload) => sendJson<JobRecord>("/benchmarks/jobs", payload),
  jobs: () => getJson<JobRecord[]>("/jobs"),
  jobLogs: (jobId: string) => getJson<{ logs: string[] }>(`/jobs/${jobId}/logs`),
  runLog: (experimentId: string) => getJson<ExperimentRunLog>(`/experiments/${experimentId}/run-log`),
  generateReport: (experimentId: string) =>
    sendJson<ReportRecord>(`/experiments/${experimentId}/reports`, { template: "internal" }),
  downloadReport: (reportId: string, format: "markdown" | "pdf" | "docx") =>
    getJson<ReportDownload>(`/reports/${reportId}/download?format=${format}`),
  artifacts: () => getJson<ArtifactRecord[]>("/artifacts")
};
