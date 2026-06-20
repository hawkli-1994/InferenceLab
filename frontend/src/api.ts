import type {
  AgentSettings,
  AgentSettingsUpdate,
  AgentSettingsValidation,
  ArtifactRecord,
  BootstrapPayload,
  BenchmarkJobPayload,
  BootstrapRun,
  CompanyReport,
  DiscoverySession,
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

async function getText(path: string): Promise<string> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.text();
}

async function sendJson<T>(path: string, body: unknown = {}, method = "POST"): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
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
  discoverySessions: () => getJson<DiscoverySession[]>("/discovery-sessions"),
  experiments: () => getJson<Experiment[]>("/experiments"),
  trials: (experimentId: string) => getJson<Trial[]>(`/experiments/${experimentId}/trials`),
  metrics: (experimentId: string) => getJson<MetricsSummary[]>(`/experiments/${experimentId}/metrics`),
  companyReport: (experimentId: string) =>
    getJson<CompanyReport>(`/experiments/${experimentId}/company-report`),
  exportCompanyReportCsv: (experimentId: string) =>
    getText(`/experiments/${experimentId}/company-report/export`),
  reports: (experimentId?: string) =>
    getJson<ReportRecord[]>(experimentId ? `/reports?experiment_id=${experimentId}` : "/reports"),
  seedDemoData: () => sendJson<Record<string, number>>("/dev/seed-demo-data"),
  createMachine: (payload: MachineCreatePayload) => sendJson<Machine>("/machines", payload),
  agentSettings: () => getJson<AgentSettings>("/agent-settings"),
  updateAgentSettings: (payload: AgentSettingsUpdate) =>
    sendJson<AgentSettings>("/agent-settings", payload, "PUT"),
  validateAgentSettings: (payload: AgentSettingsUpdate) =>
    sendJson<AgentSettingsValidation>("/agent-settings/validate", payload),
  probeMachine: (machineId: string, dryRun = true) =>
    sendJson<MachineSnapshot>(`/machines/${machineId}/probe?dry_run=${dryRun}`, {}),
  runDiscoverySession: (machineId: string, dryRun = true) =>
    sendJson<DiscoverySession>(
      `/machines/${machineId}/discovery-sessions?dry_run=${dryRun}`,
      {}
    ),
  bootstrapMachine: (machineId: string, payload: BootstrapPayload) =>
    sendJson<BootstrapRun>(`/machines/${machineId}/bootstrap`, payload),
  runPiEnvironmentWorkflow: (
    machineId: string,
    payload: { profile: string; dry_run: boolean; goal?: string }
  ) =>
    sendJson<BootstrapRun>(`/machines/${machineId}/bootstrap`, {
      profile: payload.profile,
      dry_run: payload.dry_run,
      strategy: "pi_workflow",
      pi_workflow_goal: payload.goal
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
