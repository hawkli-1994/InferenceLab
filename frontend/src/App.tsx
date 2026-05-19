import ReactECharts from "echarts-for-react";
import {
  Activity,
  BarChart3,
  Boxes,
  ClipboardList,
  FileText,
  GitCompare,
  HardDrive,
  Plus,
  Server,
  TerminalSquare
} from "lucide-react";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ElementType, ReactNode } from "react";

import { api } from "./api";
import type { Experiment, Machine, MetricsSummary } from "./types";

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
  return (
    <section className="stack">
      <header className="page-head">
        <div>
          <h1>Machine Pool</h1>
          <p>SSH onboarding records, machine profiles, and current readiness.</p>
        </div>
        <button className="primary">
          <Plus size={16} /> Add Machine
        </button>
      </header>
      <div className="split">
        <form className="panel form-grid">
          <label>
            Name
            <input defaultValue="lab-a100-02" />
          </label>
          <label>
            Host
            <input defaultValue="10.0.0.11" />
          </label>
          <label>
            User
            <input defaultValue="seed" />
          </label>
          <label>
            Runtime
            <select defaultValue="both">
              <option value="both">container + bare metal</option>
              <option value="container">container</option>
              <option value="bare_metal">bare metal</option>
            </select>
          </label>
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
        <p>{machines[0]?.name ?? "No machine"} · Full profile · dry-run enabled</p>
      </div>
    </section>
  );
}

function ExperimentsView({ machines, experiments }: { machines: Machine[]; experiments: Experiment[] }) {
  return (
    <section className="stack">
      <header className="page-head">
        <div>
          <h1>Create Experiment</h1>
          <p>Build a reproducible RunSpec before launching trials.</p>
        </div>
        <button className="primary">
          <TerminalSquare size={16} /> Create
        </button>
      </header>
      <div className="split">
        <form className="panel form-grid">
          <label>
            Machine
            <select defaultValue={machines[0]?.id}>
              {machines.map((machine) => (
                <option value={machine.id} key={machine.id}>
                  {machine.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Framework
            <select defaultValue="vllm">
              <option value="vllm">vLLM</option>
              <option value="sglang">SGLang</option>
            </select>
          </label>
          <label>
            Runtime
            <select defaultValue="container">
              <option value="container">container</option>
              <option value="bare_metal">bare metal</option>
            </select>
          </label>
          <label>
            Goal
            <select defaultValue="max_throughput">
              <option value="max_throughput">maximum throughput</option>
              <option value="lowest_p99">lowest P99 latency</option>
            </select>
          </label>
        </form>
        <div className="panel">
          <h2>Latest RunSpec</h2>
          <pre>{JSON.stringify(experiments[0]?.reproducibility ?? {}, null, 2)}</pre>
        </div>
      </div>
    </section>
  );
}

function MetricsChart({ metrics }: { metrics: MetricsSummary[] }) {
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
  return <ReactECharts option={option} className="chart" />;
}

function RunsView({ experiment, metrics }: { experiment?: Experiment; metrics: MetricsSummary[] }) {
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
          <pre>job started{"\n"}trial 1 succeeded{"\n"}trial 2 succeeded{"\n"}report artifact ready</pre>
        </div>
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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reports"] })
  });
  const reports = useQuery({ queryKey: ["reports"], queryFn: api.reports });

  return (
    <section className="stack">
      <header className="page-head">
        <div>
          <h1>Reports</h1>
          <p>Markdown source with PDF/DOCX artifact interfaces.</p>
        </div>
        <button className="primary" onClick={() => reportMutation.mutate()}>
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
  const experiments = useQuery({ queryKey: ["experiments"], queryFn: api.experiments });
  const activeExperiment = experiments.data?.[0];
  const metrics = useQuery({
    queryKey: ["metrics", activeExperiment?.id],
    queryFn: () => api.metrics(activeExperiment?.id ?? "experiment-container")
  });

  return (
    <Shell view={view} setView={setView}>
      {view === "machines" ? <MachinesView machines={machines.data ?? []} /> : null}
      {view === "bootstrap" ? <BootstrapView machines={machines.data ?? []} /> : null}
      {view === "experiments" ? (
        <ExperimentsView machines={machines.data ?? []} experiments={experiments.data ?? []} />
      ) : null}
      {view === "runs" ? <RunsView experiment={activeExperiment} metrics={metrics.data ?? []} /> : null}
      {view === "compare" ? (
        <CompareView experiments={experiments.data ?? []} metrics={metrics.data ?? []} />
      ) : null}
      {view === "history" ? <HistoryView experiments={experiments.data ?? []} /> : null}
      {view === "reports" ? <ReportsView experiment={activeExperiment} /> : null}
    </Shell>
  );
}
