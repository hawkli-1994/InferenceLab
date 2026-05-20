import type {
  BootstrapRun,
  Experiment,
  ExperimentCreatePayload,
  ExperimentPlan,
  ExperimentRunLog,
  Machine,
  MachineCreatePayload,
  MetricsSummary,
  ModelCreatePayload,
  ModelRecord,
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
  probeMachine: (machineId: string) => sendJson<Record<string, unknown>>(`/machines/${machineId}/probe`),
  bootstrapMachine: (machineId: string, profile: string) =>
    sendJson<BootstrapRun>(`/machines/${machineId}/bootstrap`, { profile, dry_run: true }),
  createModel: (payload: ModelCreatePayload) => sendJson<ModelRecord>("/models", payload),
  planExperiment: (payload: ExperimentCreatePayload) =>
    sendJson<ExperimentPlan>("/experiments/plan", { run_spec: payload.run_spec, budget: payload.budget }),
  createExperiment: (payload: ExperimentCreatePayload) =>
    sendJson<Experiment>("/experiments", payload),
  runLog: (experimentId: string) => getJson<ExperimentRunLog>(`/experiments/${experimentId}/run-log`),
  generateReport: (experimentId: string) =>
    sendJson<ReportRecord>(`/experiments/${experimentId}/reports`, { template: "internal" })
};
