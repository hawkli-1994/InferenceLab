import * as echarts from "echarts";
import {
  Activity,
  BarChart3,
  Boxes,
  ClipboardList,
  Database,
  FileText,
  GitCompare,
  HardDrive,
  Play,
  Plus,
  RotateCw,
  Search,
  Server,
  TerminalSquare
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ElementType, ReactNode } from "react";

import { api } from "./api";
import type {
  BootstrapRun,
  Experiment,
  ExperimentCreatePayload,
  ExperimentPlan,
  ExperimentRunLog,
  Machine,
  MetricsSummary,
  ModelRecord,
  RuntimeMode,
  Trial
} from "./types";

type View = "machines" | "bootstrap" | "experiments" | "runs" | "compare" | "history" | "reports";

const navItems: Array<{ id: View; label: string; icon: ElementType }> = [
  { id: "machines", label: "Machines", icon: Server },
  { id: "bootstrap", label: "Bootstrap", icon: Boxes },
  { id: "experiments", label: "Create", icon: Plus },
  { id: "runs", label: "Runs", icon: Activity },
  { id: "compare", label: "Compare", icon: GitCompare },
  { id: "history", label: "History", icon: ClipboardList },
  { id: "reports", label: "Reports", icon: FileText }
];

function numberValue(value: FormDataEntryValue | null, fallback: number) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function StatusPill({ status }: { status: string }) {
  return <span className={`status status-${status}`}>{status}</span>;
}

function Shell({
  view,
  setView,
  children
}: {
  view: View;
  setView: (view: View) => void;
  children: ReactNode;
}) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <HardDrive size={24} />
          <div>
            <strong>InferenceLab</strong>
            <span>ModelBench Agent</span>
          </div>
        </div>
        <nav>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                className={view === item.id ? "nav-item active" : "nav-item"}
                title={item.label}
                onClick={() => setView(item.id)}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>
      <main>{children}</main>
    </div>
  );
}

function MachinesView({ machines }: { machines: Machine[] }) {
  const queryClient = useQueryClient();
  const createMachine = useMutation({
    mutationFn: (formData: FormData) =>
      api.createMachine({
        name: String(formData.get("name") ?? "lab-a100-02"),
        host: String(formData.get("host") ?? "10.0.0.11"),
        port: numberValue(formData.get("port"), 22),
        username: String(formData.get("username") ?? "seed"),
        runtime_mode: String(formData.get("runtime_mode") ?? "both") as RuntimeMode,
        credential: {
          credential_type: "password",
          secret: String(formData.get("secret") ?? "seed")
        }
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["machines"] })
  });
  const probeMachine = useMutation({
    mutationFn: (machineId: string) => api.probeMachine(machineId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["machines"] })
  });
  const seedDemoData = useMutation({
    mutationFn: api.seedDemoData,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["machines"] });
      queryClient.invalidateQueries({ queryKey: ["models"] });
      queryClient.invalidateQueries({ queryKey: ["bootstrap-runs"] });
      queryClient.invalidateQueries({ queryKey: ["experiments"] });
      queryClient.invalidateQueries({ queryKey: ["reports"] });
    }
  });

  return (
    <section className="stack">
      <header className="page-head">
        <div>
          <h1>Machine Pool</h1>
          <p>SSH onboarding records, machine profiles, and current readiness.</p>
        </div>
        <button className="secondary" onClick={() => seedDemoData.mutate()} disabled={seedDemoData.isPending}>
          <Database size={16} /> {seedDemoData.isPending ? "Seeding" : "Seed DB"}
        </button>
      </header>
      <div className="split">
        <form
          className="panel form-grid"
          onSubmit={(event) => {
            event.preventDefault();
            createMachine.mutate(new FormData(event.currentTarget));
          }}
        >
          <label>
            Name
            <input name="name" defaultValue="lab-a100-02" />
          </label>
          <label>
            Host
            <input name="host" defaultValue="10.0.0.11" />
          </label>
          <label>
            User
            <input name="username" defaultValue="seed" />
          </label>
          <label>
            Port
            <input name="port" type="number" min="1" max="65535" defaultValue="22" />
          </label>
          <label>
            Password
            <input name="secret" type="password" defaultValue="seed" />
          </label>
          <label>
            Runtime
            <select name="runtime_mode" defaultValue="both">
              <option value="both">container + bare metal</option>
              <option value="container">container</option>
              <option value="bare_metal">bare metal</option>
            </select>
          </label>
          <button className="primary form-action" disabled={createMachine.isPending}>
            <Plus size={16} /> {createMachine.isPending ? "Adding" : "Add Machine"}
          </button>
          <span className="form-note">{createMachine.isError ? "API request failed" : ""}</span>
        </form>
        <div className="panel table-panel">
          <table>
            <thead>
              <tr>
                <th>Machine</th>
                <th>Host</th>
                <th>Status</th>
                <th>Runtime</th>
                <th>Fingerprint</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {machines.map((machine) => (
                <tr key={machine.id}>
                  <td>{machine.name}</td>
                  <td>{machine.host}</td>
                  <td>
                    <StatusPill status={machine.status} />
                  </td>
                  <td>{machine.runtime_mode}</td>
                  <td className="mono">{machine.fingerprint ?? "pending"}</td>
                  <td>
                    <button className="icon-button" title="Probe machine" onClick={() => probeMachine.mutate(machine.id)}>
                      <Search size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function BootstrapView({ machines }: { machines: Machine[] }) {
  const queryClient = useQueryClient();
  const [machineId, setMachineId] = useState("");
  const [profile, setProfile] = useState("full");
  const bootstrapRuns = useQuery({ queryKey: ["bootstrap-runs"], queryFn: api.bootstrapRuns });
  const selectedMachineId = machineId || machines[0]?.id || "";
  const runBootstrap = useMutation({
    mutationFn: () => api.bootstrapMachine(selectedMachineId, profile),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bootstrap-runs"] });
      queryClient.invalidateQueries({ queryKey: ["machines"] });
    }
  });
  const latestRun = bootstrapRuns.data?.[0] as BootstrapRun | undefined;

  return (
    <section className="stack">
      <header className="page-head">
        <div>
          <h1>Bootstrap Profiles</h1>
          <p>B1-B7 dry-run execution with structured step output.</p>
        </div>
      </header>
      <div className="panel flow">
        {["B1 Access", "B2 Source", "B3 Package", "B4 Storage", "B5 Container", "B6 Baseline", "B7 Bare Metal"].map(
          (step, index) => (
            <div className="flow-step" key={step}>
              <span>{index + 1}</span>
              <strong>{step}</strong>
              <small>detect / apply / verify</small>
            </div>
          )
        )}
      </div>
      <div className="panel">
        <h2>Target</h2>
        <div className="inline-controls">
          <select value={selectedMachineId} onChange={(event) => setMachineId(event.target.value)}>
            {machines.length === 0 ? (
              <option value="">No machines</option>
            ) : (
              machines.map((machine) => (
                <option value={machine.id} key={machine.id}>
                  {machine.name}
                </option>
              ))
            )}
          </select>
          <select value={profile} onChange={(event) => setProfile(event.target.value)}>
            <option value="minimal">minimal</option>
            <option value="standard_container">standard container</option>
            <option value="standard_bare_metal">standard bare metal</option>
            <option value="full">full</option>
          </select>
          <button className="primary" disabled={!selectedMachineId || runBootstrap.isPending} onClick={() => runBootstrap.mutate()}>
            <Play size={16} /> {runBootstrap.isPending ? "Running" : "Run Dry-Run"}
          </button>
        </div>
      </div>
      <div className="panel table-panel">
        <h2>Latest Step Output</h2>
        <table>
          <thead>
            <tr>
              <th>Module</th>
              <th>Status</th>
              <th>Changed Files</th>
              <th>Failure Hint</th>
            </tr>
          </thead>
          <tbody>
            {(latestRun?.step_results ?? []).map((step) => (
              <tr key={`${latestRun?.id}-${step.id}`}>
                <td>{step.name}</td>
                <td>
                  <StatusPill status={step.status} />
                </td>
                <td>{step.changed_files.join(", ") || "none"}</td>
                <td>{step.failure_hint ?? "none"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ExperimentsView({
  machines,
  models,
  experiments
}: {
  machines: Machine[];
  models: ModelRecord[];
  experiments: Experiment[];
}) {
  const queryClient = useQueryClient();
  const [plan, setPlan] = useState<ExperimentPlan | null>(null);
  const [selectedMachineId, setSelectedMachineId] = useState("");
  const [selectedModelId, setSelectedModelId] = useState("");
  const machineId = selectedMachineId || machines[0]?.id || "";
  const modelId = selectedModelId || models[0]?.id || "";
  const createModel = useMutation({
    mutationFn: (formData: FormData) =>
      api.createModel({
        name: String(formData.get("model_name") ?? "Qwen3-32B"),
        source: "mock",
        format: "safetensors",
        cache_path: String(formData.get("cache_path") ?? "/data/models/qwen3-32b"),
        metadata: { owner: "workbench" }
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["models"] })
  });
  const planExperiment = useMutation({
    mutationFn: (payload: ExperimentCreatePayload) => api.planExperiment(payload),
    onSuccess: setPlan
  });
  const createExperiment = useMutation({
    mutationFn: (payload: ExperimentCreatePayload) => api.createExperiment(payload),
    onSuccess: (experiment) => {
      queryClient.invalidateQueries({ queryKey: ["experiments"] });
      queryClient.invalidateQueries({ queryKey: ["metrics", experiment.id] });
      queryClient.invalidateQueries({ queryKey: ["trials", experiment.id] });
      queryClient.invalidateQueries({ queryKey: ["run-log", experiment.id] });
    }
  });
  const buildPayload = (formData: FormData): ExperimentCreatePayload => ({
    name: String(formData.get("name") ?? "container baseline"),
    goal: String(formData.get("goal") ?? "max_throughput"),
    budget: { max_trials: numberValue(formData.get("max_trials"), 2) },
    run_spec: {
      machine_id: String(formData.get("machine_id") ?? machineId),
      model_id: String(formData.get("model_id") ?? modelId),
      runtime_mode: String(formData.get("runtime_mode") ?? "container") as "container" | "bare_metal",
      framework: String(formData.get("framework") ?? "vllm") as "vllm" | "sglang",
      framework_version: String(formData.get("framework_version") ?? "0.9.0-mock"),
      prompt_dataset: String(formData.get("prompt_dataset") ?? "mock_prompts_v1"),
      benchmark_version: "inflab-bench-mock-v1",
      framework_params: {
        tensor_parallel_size: numberValue(formData.get("tensor_parallel_size"), 1),
        gpu_memory_utilization: numberValue(formData.get("gpu_memory_utilization"), 0.88),
        max_num_seqs: numberValue(formData.get("max_num_seqs"), 128)
      }
    }
  });

  return (
    <section className="stack">
      <header className="page-head">
        <div>
          <h1>Create Experiment</h1>
          <p>Build a reproducible RunSpec before launching trials.</p>
        </div>
      </header>
      <div className="split">
        <form
          className="panel form-grid"
          onSubmit={(event) => {
            event.preventDefault();
            createModel.mutate(new FormData(event.currentTarget));
          }}
        >
          <label>
            Model
            <input name="model_name" defaultValue="Qwen3-32B" />
          </label>
          <label>
            Cache Path
            <input name="cache_path" defaultValue="/data/models/qwen3-32b" />
          </label>
          <button className="primary form-action" disabled={createModel.isPending}>
            <Database size={16} /> {createModel.isPending ? "Registering" : "Register Model"}
          </button>
          <span className="form-note">{models.length} models registered</span>
        </form>
        <form
          className="panel form-grid"
          onSubmit={(event) => {
            event.preventDefault();
            createExperiment.mutate(buildPayload(new FormData(event.currentTarget)));
          }}
        >
          <label>
            Name
            <input name="name" defaultValue="container baseline" />
          </label>
          <label>
            Machine
            <select name="machine_id" value={machineId} onChange={(event) => setSelectedMachineId(event.target.value)}>
              {machines.length === 0 ? (
                <option value="">No machines</option>
              ) : (
                machines.map((machine) => (
                  <option value={machine.id} key={machine.id}>
                    {machine.name}
                  </option>
                ))
              )}
            </select>
          </label>
          <label>
            Model
            <select name="model_id" value={modelId} onChange={(event) => setSelectedModelId(event.target.value)}>
              {models.length === 0 ? (
                <option value="">No models</option>
              ) : (
                models.map((model) => (
                  <option value={model.id} key={model.id}>
                    {model.name}
                  </option>
                ))
              )}
            </select>
          </label>
          <label>
            Framework
            <select name="framework" defaultValue="vllm">
              <option value="vllm">vLLM</option>
              <option value="sglang">SGLang</option>
            </select>
          </label>
          <label>
            Runtime
            <select name="runtime_mode" defaultValue="container">
              <option value="container">container</option>
              <option value="bare_metal">bare metal</option>
            </select>
          </label>
          <label>
            Goal
            <select name="goal" defaultValue="max_throughput">
              <option value="max_throughput">maximum throughput</option>
              <option value="lowest_p99">lowest P99 latency</option>
            </select>
          </label>
          <label>
            Framework Version
            <input name="framework_version" defaultValue="0.9.0-mock" />
          </label>
          <label>
            Prompt Dataset
            <input name="prompt_dataset" defaultValue="mock_prompts_v1" />
          </label>
          <label>
            Tensor Parallel
            <input name="tensor_parallel_size" type="number" min="1" defaultValue="4" />
          </label>
          <label>
            GPU Memory
            <input name="gpu_memory_utilization" type="number" min="0.1" max="1" step="0.01" defaultValue="0.88" />
          </label>
          <label>
            Max Seqs
            <input name="max_num_seqs" type="number" min="1" defaultValue="128" />
          </label>
          <label>
            Max Trials
            <input name="max_trials" type="number" min="1" max="8" defaultValue="2" />
          </label>
          <div className="form-actions">
            <button
              className="secondary"
              type="button"
              disabled={!machineId || !modelId || planExperiment.isPending}
              onClick={(event) => {
                const form = event.currentTarget.form;
                if (form) {
                  planExperiment.mutate(buildPayload(new FormData(form)));
                }
              }}
            >
              <RotateCw size={16} /> {planExperiment.isPending ? "Planning" : "Preview"}
            </button>
            <button className="primary" disabled={!machineId || !modelId || createExperiment.isPending}>
              <TerminalSquare size={16} /> {createExperiment.isPending ? "Creating" : "Create"}
            </button>
          </div>
        </form>
      </div>
      <div className="split">
        <div className="panel">
          <h2>Candidate Preview</h2>
          <pre>{JSON.stringify(plan ?? experiments[0]?.reproducibility ?? {}, null, 2)}</pre>
        </div>
        <div className="panel table-panel">
          <h2>Recent Experiments</h2>
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Runtime</th>
                <th>Status</th>
                <th>Candidates</th>
              </tr>
            </thead>
            <tbody>
              {experiments.slice(0, 5).map((experiment) => (
                <tr key={experiment.id}>
                  <td>{experiment.name}</td>
                  <td>{experiment.runtime_mode}</td>
                  <td>
                    <StatusPill status={experiment.status} />
                  </td>
                  <td>{String(experiment.reproducibility.candidate_count ?? "n/a")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

function MetricsChart({ metrics }: { metrics: MetricsSummary[] }) {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const option = useMemo(
    () => ({
      grid: { left: 44, right: 20, top: 24, bottom: 36 },
      tooltip: {},
      xAxis: { type: "category", data: metrics.map((metric) => metric.trial_id ?? "baseline") },
      yAxis: { type: "value" },
      series: [
        {
          type: "bar",
          name: "tokens/s",
          data: metrics.map((metric) => metric.tokens_per_second),
          itemStyle: { color: "#2f6f6b" }
        }
      ]
    }),
    [metrics]
  );
  useEffect(() => {
    if (!chartRef.current) {
      return;
    }
    const chart = echarts.init(chartRef.current);
    chart.setOption(option);
    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [option]);
  return <div ref={chartRef} className="chart" />;
}

function RunsView({
  experiment,
  metrics,
  trials,
  runLog
}: {
  experiment?: Experiment;
  metrics: MetricsSummary[];
  trials: Trial[];
  runLog?: ExperimentRunLog;
}) {
  return (
    <section className="stack">
      <header className="page-head">
        <div>
          <h1>Experiment Run</h1>
          <p>Trials, logs, normalized metrics, and launch command.</p>
        </div>
        {experiment ? <StatusPill status={experiment.status} /> : null}
      </header>
      <div className="split">
        <div className="panel">
          <h2>Metrics</h2>
          <MetricsChart metrics={metrics} />
        </div>
        <div className="panel">
          <h2>Logs</h2>
          <pre>{(runLog?.lines ?? ["No experiment selected"]).join("\n")}</pre>
        </div>
      </div>
      <div className="panel table-panel">
        <h2>Trials</h2>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Status</th>
              <th>Params</th>
              <th>Command</th>
            </tr>
          </thead>
          <tbody>
            {trials.map((trial) => (
              <tr key={trial.id}>
                <td>{trial.trial_index}</td>
                <td>
                  <StatusPill status={trial.status} />
                </td>
                <td className="mono">{JSON.stringify(trial.params)}</td>
                <td className="mono">{trial.launch_command}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="panel">
        <h2>Launch Command</h2>
        <code>{experiment?.launch_command ?? "No experiment selected"}</code>
      </div>
    </section>
  );
}

function CompareView({ experiments, metrics }: { experiments: Experiment[]; metrics: MetricsSummary[] }) {
  const container = experiments.find((experiment) => experiment.runtime_mode === "container");
  const bare = experiments.find((experiment) => experiment.runtime_mode === "bare_metal");
  return (
    <section className="stack">
      <header className="page-head">
        <div>
          <h1>Container vs Bare Metal</h1>
          <p>Same machine, model hash, prompts, benchmark version, and parameter space.</p>
        </div>
      </header>
      <div className="panel comparison">
        <div>
          <strong>{container?.name ?? "container run"}</strong>
          <span>{metrics.find((metric) => metric.experiment_id === container?.id)?.tokens_per_second ?? 0} tokens/s</span>
        </div>
        <div>
          <strong>{bare?.name ?? "bare-metal run"}</strong>
          <span>{metrics.find((metric) => metric.experiment_id === bare?.id)?.tokens_per_second ?? 0} tokens/s</span>
        </div>
      </div>
    </section>
  );
}

function HistoryView({ experiments }: { experiments: Experiment[] }) {
  return (
    <section className="stack">
      <header className="page-head">
        <div>
          <h1>Experiment History</h1>
          <p>Reproducible runs and past benchmark baselines.</p>
        </div>
      </header>
      <div className="panel table-panel">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Runtime</th>
              <th>Framework</th>
              <th>Prompt Set</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {experiments.map((experiment) => (
              <tr key={experiment.id}>
                <td>{experiment.name}</td>
                <td>{experiment.runtime_mode}</td>
                <td>{experiment.framework}</td>
                <td>{experiment.prompt_dataset}</td>
                <td>
                  <StatusPill status={experiment.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ReportsView({ experiment }: { experiment?: Experiment }) {
  const queryClient = useQueryClient();
  const reportMutation = useMutation({
    mutationFn: () => api.generateReport(experiment?.id ?? "experiment-container"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reports", experiment?.id] })
  });
  const reports = useQuery({
    queryKey: ["reports", experiment?.id],
    queryFn: () => api.reports(experiment?.id)
  });

  return (
    <section className="stack">
      <header className="page-head">
        <div>
          <h1>Reports</h1>
          <p>Markdown source with PDF/DOCX artifact interfaces.</p>
        </div>
        <button className="primary" disabled={!experiment || reportMutation.isPending} onClick={() => reportMutation.mutate()}>
          <FileText size={16} /> Generate
        </button>
      </header>
      <div className="panel table-panel">
        <table>
          <thead>
            <tr>
              <th>Template</th>
              <th>Status</th>
              <th>Artifact</th>
            </tr>
          </thead>
          <tbody>
            {(reports.data ?? []).map((report) => (
              <tr key={report.id}>
                <td>{report.template}</td>
                <td>
                  <StatusPill status={report.status} />
                </td>
                <td>{report.artifact_id ?? "pending"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function App() {
  const [view, setView] = useState<View>("machines");
  const machines = useQuery({ queryKey: ["machines"], queryFn: api.machines });
  const models = useQuery({ queryKey: ["models"], queryFn: api.models });
  const experiments = useQuery({ queryKey: ["experiments"], queryFn: api.experiments });
  const activeExperiment = experiments.data?.[0];
  const metrics = useQuery({
    queryKey: ["metrics", activeExperiment?.id],
    queryFn: () => api.metrics(activeExperiment?.id ?? ""),
    enabled: Boolean(activeExperiment)
  });
  const trials = useQuery({
    queryKey: ["trials", activeExperiment?.id],
    queryFn: () => api.trials(activeExperiment?.id ?? ""),
    enabled: Boolean(activeExperiment)
  });
  const runLog = useQuery({
    queryKey: ["run-log", activeExperiment?.id],
    queryFn: () => api.runLog(activeExperiment?.id ?? ""),
    enabled: Boolean(activeExperiment)
  });

  return (
    <Shell view={view} setView={setView}>
      {view === "machines" ? <MachinesView machines={machines.data ?? []} /> : null}
      {view === "bootstrap" ? <BootstrapView machines={machines.data ?? []} /> : null}
      {view === "experiments" ? (
        <ExperimentsView
          machines={machines.data ?? []}
          models={models.data ?? []}
          experiments={experiments.data ?? []}
        />
      ) : null}
      {view === "runs" ? (
        <RunsView
          experiment={activeExperiment}
          metrics={metrics.data ?? []}
          trials={trials.data ?? []}
          runLog={runLog.data}
        />
      ) : null}
      {view === "compare" ? (
        <CompareView experiments={experiments.data ?? []} metrics={metrics.data ?? []} />
      ) : null}
      {view === "history" ? <HistoryView experiments={experiments.data ?? []} /> : null}
      {view === "reports" ? <ReportsView experiment={activeExperiment} /> : null}
    </Shell>
  );
}
