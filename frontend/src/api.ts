import {
  mockBootstrapRuns,
  mockExperiments,
  mockMachines,
  mockMetrics,
  mockModels,
  mockReports,
  mockTrials
} from "./mock";
import type { BootstrapRun, Experiment, Machine, MetricsSummary, ModelRecord, ReportRecord, Trial } from "./types";

const API_BASE = "/api/v1";

async function getJson<T>(path: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(`${API_BASE}${path}`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    if (data && Array.isArray(data.items)) {
      return data.items as T;
    }
    return data as T;
  } catch {
    return fallback;
  }
}

export const api = {
  machines: () => getJson<Machine[]>("/machines", mockMachines),
  models: () => getJson<ModelRecord[]>("/models", mockModels),
  bootstrapRuns: () => getJson<BootstrapRun[]>("/bootstrap-runs", mockBootstrapRuns),
  experiments: () => getJson<Experiment[]>("/experiments", mockExperiments),
  trials: (experimentId: string) =>
    getJson<Trial[]>(
      `/experiments/${experimentId}/trials`,
      mockTrials.filter((trial) => trial.experiment_id === experimentId)
    ),
  metrics: (experimentId: string) =>
    getJson<MetricsSummary[]>(
      `/experiments/${experimentId}/metrics`,
      mockMetrics.filter((metric) => metric.experiment_id === experimentId)
    ),
  reports: () => Promise.resolve(mockReports),
  generateReport: async (experimentId: string): Promise<ReportRecord> => {
    try {
      const response = await fetch(`${API_BASE}/experiments/${experimentId}/reports`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ template: "internal" })
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      return (await response.json()) as ReportRecord;
    } catch {
      return mockReports[0];
    }
  }
};
