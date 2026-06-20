import * as echarts from "echarts";
import {
  Activity,
  BarChart3,
  Boxes,
  ClipboardList,
  Database,
  Download,
  FileText,
  GitCompare,
  HardDrive,
  Play,
  Plus,
  RotateCw,
  Save,
  Search,
  Server,
  ShieldCheck,
  TerminalSquare,
} from "lucide-react";
import { createContext, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ElementType, ReactNode } from "react";

import { api } from "./api";
import { initialLocale, translate, type Locale, type MessageKey } from "./i18n";
import type {
  AgentSettings,
  AgentSettingsUpdate,
  BenchmarkKind,
  BootstrapRun,
  ExecutionMode,
  Experiment,
  ExperimentCreatePayload,
  ExperimentMode,
  ExperimentPlan,
  ExperimentRunLog,
  JobRecord,
  LLMProviderName,
  Machine,
  MetricsSummary,
  ModelDistributeResult,
  ModelRecord,
  ModelSource,
  RuntimeMode,
  Trial
} from "./types";

type View = "machines" | "bootstrap" | "experiments" | "runs" | "compare" | "history" | "reports";
type EnvironmentSetupMode = "pi_workflow" | "scripted";

const navItems: Array<{ id: View; labelKey: MessageKey; icon: ElementType }> = [
  { id: "machines", labelKey: "machines", icon: Server },
  { id: "bootstrap", labelKey: "bootstrap", icon: Boxes },
  { id: "experiments", labelKey: "create", icon: Plus },
  { id: "runs", labelKey: "runs", icon: Activity },
  { id: "compare", labelKey: "compare", icon: GitCompare },
  { id: "history", labelKey: "history", icon: ClipboardList },
  { id: "reports", labelKey: "reports", icon: FileText }
];

type I18nState = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: MessageKey) => string;
};

const I18nContext = createContext<I18nState | null>(null);

function useI18n() {
  const value = useContext(I18nContext);
  if (!value) {
    throw new Error("I18nContext is not available");
  }
  return value;
}

function numberValue(value: FormDataEntryValue | null, fallback: number) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function optionalNumberValue(value: FormDataEntryValue | null) {
  const raw = String(value ?? "").trim();
  if (!raw) {
    return undefined;
  }
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function runSpecFromExperiment(experiment: Experiment) {
  return {
    machine_id: experiment.machine_id,
    model_id: experiment.model_id,
    runtime_mode: experiment.runtime_mode as Exclude<RuntimeMode, "both">,
    framework: experiment.framework as "vllm" | "sglang",
    framework_version: experiment.framework_version,
    framework_params: experiment.framework_params,
    prompt_dataset: experiment.prompt_dataset,
    benchmark_version: "inflab-bench-real-v1"
  };
}

function agentSettingsToDraft(settings: AgentSettings): AgentSettingsUpdate {
  return {
    llm: {
      provider: settings.llm.provider,
      base_url: settings.llm.base_url ?? "",
      model: settings.llm.model ?? "",
      api_key: "",
      clear_api_key: false
    },
    pi: {
      ...settings.pi
    }
  };
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
  const { locale, setLocale, t } = useI18n();
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <HardDrive size={24} />
          <div>
            <strong>InferenceLab</strong>
            <span>{t("appSubtitle")}</span>
          </div>
        </div>
        <label className="locale-switch">
          <span>{t("language")}</span>
          <select value={locale} onChange={(event) => setLocale(event.target.value as Locale)}>
            <option value="en">English</option>
            <option value="zh">中文</option>
          </select>
        </label>
        <nav>
          {navItems.map((item) => {
            const Icon = item.icon;
            const label = t(item.labelKey);
            return (
              <button
                key={item.id}
                className={view === item.id ? "nav-item active" : "nav-item"}
                title={label}
                onClick={() => setView(item.id)}
              >
                <Icon size={18} />
                <span>{label}</span>
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
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [probeDryRun, setProbeDryRun] = useState(true);
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
    mutationFn: (machineId: string) => api.probeMachine(machineId, probeDryRun),
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
          <h1>{t("machinePool")}</h1>
          <p>{t("machinePoolDesc")}</p>
        </div>
        <div className="toolbar">
          <label className="check-row">
            <input
              type="checkbox"
              checked={probeDryRun}
              onChange={(event) => setProbeDryRun(event.target.checked)}
            />
            {t("dryRunProbe")}
          </label>
          <button className="secondary" onClick={() => seedDemoData.mutate()} disabled={seedDemoData.isPending}>
            <Database size={16} /> {seedDemoData.isPending ? t("seeding") : t("seedDb")}
          </button>
        </div>
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
            {t("name")}
            <input name="name" defaultValue="lab-a100-02" />
          </label>
          <label>
            {t("host")}
            <input name="host" defaultValue="10.0.0.11" />
          </label>
          <label>
            {t("user")}
            <input name="username" defaultValue="seed" />
          </label>
          <label>
            {t("port")}
            <input name="port" type="number" min="1" max="65535" defaultValue="22" />
          </label>
          <label>
            {t("password")}
            <input name="secret" type="password" defaultValue="seed" />
          </label>
          <label>
            {t("runtime")}
            <select name="runtime_mode" defaultValue="both">
              <option value="both">container + bare metal</option>
              <option value="container">container</option>
              <option value="bare_metal">bare metal</option>
            </select>
          </label>
          <button className="primary form-action" disabled={createMachine.isPending}>
            <Plus size={16} /> {createMachine.isPending ? t("adding") : t("addMachine")}
          </button>
          <span className="form-note">{createMachine.isError ? "API request failed" : ""}</span>
        </form>
        <div className="panel table-panel">
          <table>
            <thead>
              <tr>
                <th>{t("machines")}</th>
                <th>{t("host")}</th>
                <th>{t("status")}</th>
                <th>{t("runtime")}</th>
                <th>{t("fingerprint")}</th>
                <th>{t("action")}</th>
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
                    <button
                      className="icon-button"
                      title={probeDryRun ? "Probe with dry-run profile" : "Probe over SSH"}
                      onClick={() => probeMachine.mutate(machine.id)}
                    >
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
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [machineId, setMachineId] = useState("");
  const [profile, setProfile] = useState("full");
  const [dryRun, setDryRun] = useState(true);
  const [environmentSetupMode, setEnvironmentSetupMode] =
    useState<EnvironmentSetupMode>("pi_workflow");
  const [piWorkflowGoal, setPiWorkflowGoal] = useState("");
  const bootstrapRuns = useQuery({ queryKey: ["bootstrap-runs"], queryFn: api.bootstrapRuns });
  const selectedMachineId = machineId || machines[0]?.id || "";
  const piWorkflow = environmentSetupMode === "pi_workflow";
  const runBootstrap = useMutation({
    mutationFn: () =>
      piWorkflow
        ? api.runPiEnvironmentWorkflow(selectedMachineId, {
            profile,
            dry_run: dryRun,
            goal: piWorkflowGoal.trim() || undefined
          })
        : api.bootstrapMachine(selectedMachineId, {
            profile,
            dry_run: dryRun,
            strategy: "scripted"
          }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["bootstrap-runs"] });
      queryClient.invalidateQueries({ queryKey: ["machines"] });
    }
  });
  const latestRun = bootstrapRuns.data?.[0] as BootstrapRun | undefined;
  const flowSteps = piWorkflow
    ? [
        t("workflowDiscover"),
        t("workflowPlan"),
        t("workflowApply"),
        t("workflowVerify"),
        t("workflowRecord")
      ]
    : [
        "B1 Access",
        "B2 Source",
        "B3 Package",
        "B4 Storage",
        "B5 Container",
        "B6 Baseline",
        "B7 Bare Metal"
      ];

  return (
    <section className="stack">
      <header className="page-head">
        <div>
          <h1>{t("bootstrapProfiles")}</h1>
          <p>{t("bootstrapDesc")}</p>
        </div>
      </header>
      <div className={`panel flow flow-${environmentSetupMode}`}>
        {flowSteps.map((step, index) => (
          <div className="flow-step" key={step}>
            <span>{index + 1}</span>
            <strong>{step}</strong>
            <small>
              {piWorkflow ? t("agentWorkflow") : "detect / apply / verify"}
            </small>
          </div>
        ))}
      </div>
      <div className="panel">
        <h2>{t("target")}</h2>
        <div className="setup-form">
          <div className="inline-controls setup-controls">
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
            <div className="setup-mode" aria-label={t("environmentSetupMode")}>
              <button
                type="button"
                className={environmentSetupMode === "pi_workflow" ? "active" : ""}
                onClick={() => setEnvironmentSetupMode("pi_workflow")}
              >
                <TerminalSquare size={15} /> {t("piWorkflowSetup")}
              </button>
              <button
                type="button"
                className={environmentSetupMode === "scripted" ? "active" : ""}
                onClick={() => setEnvironmentSetupMode("scripted")}
              >
                <RotateCw size={15} /> {t("scriptedSetup")}
              </button>
            </div>
            <select value={profile} onChange={(event) => setProfile(event.target.value)}>
              <option value="minimal">minimal</option>
              <option value="standard_container">standard container</option>
              <option value="standard_bare_metal">standard bare metal</option>
              <option value="full">full</option>
            </select>
            <label className="check-row">
              <input
                type="checkbox"
                checked={dryRun}
                onChange={(event) => setDryRun(event.target.checked)}
              />
              {t("dryRun")}
            </label>
            <button className="primary" disabled={!selectedMachineId || runBootstrap.isPending} onClick={() => runBootstrap.mutate()}>
              <Play size={16} />{" "}
              {runBootstrap.isPending
                ? t("running")
                : piWorkflow
                  ? dryRun
                    ? t("previewPiWorkflow")
                    : t("runPiWorkflow")
                  : dryRun
                    ? t("runDryRun")
                    : t("runSsh")}
            </button>
          </div>
          {piWorkflow ? (
            <textarea
              className="workflow-goal"
              value={piWorkflowGoal}
              maxLength={2000}
              placeholder={t("piWorkflowGoalPlaceholder")}
              onChange={(event) => setPiWorkflowGoal(event.target.value)}
            />
          ) : null}
        </div>
      </div>
      <div className="panel table-panel">
        <h2>{t("latestStepOutput")}</h2>
        <table>
          <thead>
            <tr>
              <th>{t("module")}</th>
              <th>{t("status")}</th>
              <th>{t("changedFiles")}</th>
              <th>{t("failureHint")}</th>
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

function AgentSettingsPanel() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["agent-settings"], queryFn: api.agentSettings });
  const [draft, setDraft] = useState<AgentSettingsUpdate | null>(null);

  useEffect(() => {
    if (settings.data) {
      setDraft(agentSettingsToDraft(settings.data));
    }
  }, [settings.data]);

  const saveSettings = useMutation({
    mutationFn: (payload: AgentSettingsUpdate) => api.updateAgentSettings(payload),
    onSuccess: (data) => {
      queryClient.setQueryData(["agent-settings"], data);
      setDraft(agentSettingsToDraft(data));
    }
  });
  const validateSettings = useMutation({
    mutationFn: (payload: AgentSettingsUpdate) => api.validateAgentSettings(payload)
  });

  const updateLlm = (patch: Partial<AgentSettingsUpdate["llm"]>) => {
    setDraft((current) =>
      current
        ? {
            ...current,
            llm: { ...current.llm, ...patch }
          }
        : current
    );
  };
  const updatePi = (patch: Partial<AgentSettingsUpdate["pi"]>) => {
    setDraft((current) =>
      current
        ? {
            ...current,
            pi: { ...current.pi, ...patch }
          }
        : current
    );
  };

  if (settings.isLoading || !draft) {
    return (
      <aside className="panel agent-settings-panel">
        <h2>{t("agentSettings")}</h2>
        <p>{t("running")}</p>
      </aside>
    );
  }

  const piPlan = settings.data?.pi_executor_plan;
  const workerPrompt = settings.data?.worker_prompt ?? "";
  const apiKeyStatus = settings.data?.llm.api_key_configured
    ? t("apiKeyConfigured")
    : t("apiKeyNotConfigured");

  return (
    <aside className="panel agent-settings-panel">
      <div className="panel-heading">
        <div>
          <h2>{t("agentSettings")}</h2>
          <p>{t("agentSettingsDesc")}</p>
        </div>
        {settings.data ? <StatusPill status={settings.data.pi_executor_plan.status} /> : null}
      </div>

      <div className="settings-section">
        <h3>{t("llmProvider")}</h3>
        <label>
          {t("llmProvider")}
          <select
            value={draft.llm.provider}
            onChange={(event) =>
              updateLlm({ provider: event.target.value as LLMProviderName })
            }
          >
            <option value="disabled">{t("disabledProvider")}</option>
            <option value="openai_compatible">{t("openaiCompatible")}</option>
            <option value="anthropic">{t("anthropic")}</option>
          </select>
        </label>
        <label>
          {t("baseUrl")}
          <input
            value={draft.llm.base_url ?? ""}
            disabled={draft.llm.provider === "disabled"}
            placeholder="https://api.example.com/v1"
            onChange={(event) => updateLlm({ base_url: event.target.value })}
          />
        </label>
        <label>
          {t("model")}
          <input
            value={draft.llm.model ?? ""}
            disabled={draft.llm.provider === "disabled"}
            placeholder="openai/gpt-4.1-mini"
            onChange={(event) => updateLlm({ model: event.target.value })}
          />
        </label>
        <label>
          {t("apiKey")}
          <input
            type="password"
            value={draft.llm.api_key ?? ""}
            disabled={draft.llm.provider === "disabled"}
            placeholder={apiKeyStatus}
            onChange={(event) =>
              updateLlm({ api_key: event.target.value, clear_api_key: false })
            }
          />
        </label>
        <label className="check-row">
          <input
            type="checkbox"
            checked={Boolean(draft.llm.clear_api_key)}
            disabled={!settings.data?.llm.api_key_configured}
            onChange={(event) =>
              updateLlm({ clear_api_key: event.target.checked, api_key: "" })
            }
          />
          {t("clearApiKey")}
        </label>
      </div>

      <div className="settings-section">
        <h3>{t("piAgent")}</h3>
        <label className="check-row">
          <input
            type="checkbox"
            checked={draft.pi.enabled}
            onChange={(event) => updatePi({ enabled: event.target.checked })}
          />
          {t("enabled")}
        </label>
        <label>
          {t("command")}
          <input
            value={draft.pi.command}
            disabled={!draft.pi.enabled}
            onChange={(event) => updatePi({ command: event.target.value })}
          />
        </label>
        <label>
          {t("workDir")}
          <input
            value={draft.pi.work_dir}
            disabled={!draft.pi.enabled}
            onChange={(event) => updatePi({ work_dir: event.target.value })}
          />
        </label>
        <div className="settings-grid">
          <label>
            {t("maxRounds")}
            <input
              type="number"
              min="1"
              max="200"
              value={draft.pi.max_rounds}
              disabled={!draft.pi.enabled}
              onChange={(event) => updatePi({ max_rounds: Number(event.target.value) })}
            />
          </label>
          <label>
            {t("timeoutMinutes")}
            <input
              type="number"
              min="1"
              max="1440"
              value={draft.pi.timeout_minutes}
              disabled={!draft.pi.enabled}
              onChange={(event) => updatePi({ timeout_minutes: Number(event.target.value) })}
            />
          </label>
        </div>
      </div>

      <div className="form-actions">
        <button
          className="primary"
          type="button"
          disabled={saveSettings.isPending}
          onClick={() => saveSettings.mutate(draft)}
        >
          <Save size={16} /> {saveSettings.isPending ? t("saving") : t("saveSettings")}
        </button>
        <button
          className="secondary"
          type="button"
          disabled={validateSettings.isPending}
          onClick={() => validateSettings.mutate(draft)}
        >
          <ShieldCheck size={16} />{" "}
          {validateSettings.isPending ? t("validating") : t("validateConfig")}
        </button>
      </div>

      {validateSettings.data ? (
        <div className="validation-list">
          <h3>{t("validation")}</h3>
          {validateSettings.data.checks.map((check) => (
            <div className={`validation-item validation-${check.status}`} key={check.key}>
              <strong>{check.key}</strong>
              <span>{check.message}</span>
            </div>
          ))}
        </div>
      ) : null}

      <div className="settings-section">
        <h3>{t("currentPiPlan")}</h3>
        <dl className="plan-list">
          <div>
            <dt>provider</dt>
            <dd>{piPlan?.provider ?? "n/a"}</dd>
          </div>
          <div>
            <dt>{t("command")}</dt>
            <dd>{piPlan?.command ?? "n/a"}</dd>
          </div>
          <div>
            <dt>{t("workDir")}</dt>
            <dd>{piPlan?.work_dir ?? "n/a"}</dd>
          </div>
          <div>
            <dt>{t("maxRounds")}</dt>
            <dd>{piPlan?.max_rounds ?? "n/a"}</dd>
          </div>
          <div>
            <dt>{t("timeoutMinutes")}</dt>
            <dd>{piPlan?.timeout_minutes ?? "n/a"}</dd>
          </div>
        </dl>
      </div>

      <div className="settings-section">
        <h3>{t("workerPromptPreview")}</h3>
        <pre className="prompt-preview">{workerPrompt}</pre>
      </div>
    </aside>
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
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [plan, setPlan] = useState<ExperimentPlan | null>(null);
  const [selectedMachineId, setSelectedMachineId] = useState("");
  const [selectedModelId, setSelectedModelId] = useState("");
  const [distributeDryRun, setDistributeDryRun] = useState(true);
  const [distributionResult, setDistributionResult] = useState<ModelDistributeResult | null>(null);
  const machineId = selectedMachineId || machines[0]?.id || "";
  const modelId = selectedModelId || models[0]?.id || "";
  const createModel = useMutation({
    mutationFn: (formData: FormData) =>
      api.createModel({
        name: String(formData.get("model_name") ?? "Qwen3-32B"),
        source: String(formData.get("source") ?? "mock") as ModelSource,
        format: "safetensors",
        cache_path: String(formData.get("cache_path") ?? "/data/models/qwen3-32b"),
        metadata: { owner: "workbench" }
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["models"] })
  });
  const distributeModel = useMutation({
    mutationFn: (formData: FormData) =>
      api.distributeModel(modelId, {
        machine_id: machineId,
        target_path: String(formData.get("target_path") ?? "").trim() || undefined,
        dry_run: distributeDryRun
      }),
    onSuccess: setDistributionResult
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
    mode: String(formData.get("mode") ?? "standard") as ExperimentMode,
    goal: String(formData.get("goal") ?? "max_throughput"),
    budget: { max_trials: numberValue(formData.get("max_trials"), 2) },
    run_spec: {
      machine_id: String(formData.get("machine_id") ?? machineId),
      model_id: String(formData.get("model_id") ?? modelId),
      runtime_mode: String(formData.get("runtime_mode") ?? "container") as "container" | "bare_metal",
      framework: String(formData.get("framework") ?? "vllm") as "vllm" | "sglang",
      framework_version: String(formData.get("framework_version") ?? "0.10.0"),
      prompt_dataset: String(formData.get("prompt_dataset") ?? "random"),
      benchmark_version: "inflab-bench-real-v1",
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
          <h1>{t("createExperiment")}</h1>
          <p>{t("createExperimentDesc")}</p>
        </div>
      </header>
      <div className="experiment-layout">
        <div className="experiment-main">
          <form
            className="panel form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              createModel.mutate(new FormData(event.currentTarget));
            }}
          >
            <label>
              {t("model")}
              <input name="model_name" defaultValue="Qwen3-32B" />
            </label>
            <label>
              {t("cachePath")}
              <input name="cache_path" defaultValue="/data/models/qwen3-32b" />
            </label>
            <label>
              {t("source")}
              <select name="source" defaultValue="mock">
                <option value="mock">existing path</option>
                <option value="rsync">rsync mirror</option>
                <option value="nfs">NFS mount</option>
                <option value="minio">MinIO/S3</option>
                <option value="huggingface">Hugging Face</option>
                <option value="modelscope">ModelScope</option>
              </select>
            </label>
            <button className="primary form-action" disabled={createModel.isPending}>
              <Database size={16} /> {createModel.isPending ? t("registering") : t("registerModel")}
            </button>
            <span className="form-note">{models.length} {t("modelsRegistered")}</span>
          </form>
          <form
            className="panel form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              createExperiment.mutate(buildPayload(new FormData(event.currentTarget)));
            }}
          >
            <label>
              {t("name")}
              <input name="name" defaultValue="container baseline" />
            </label>
            <label>
              {t("machines")}
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
              {t("model")}
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
              {t("framework")}
              <select name="framework" defaultValue="vllm">
                <option value="vllm">vLLM</option>
                <option value="sglang">SGLang</option>
              </select>
            </label>
            <label>
              {t("runtime")}
              <select name="runtime_mode" defaultValue="container">
                <option value="container">container</option>
                <option value="bare_metal">bare metal</option>
              </select>
            </label>
            <label>
              {t("goal")}
              <select name="goal" defaultValue="max_throughput">
                <option value="max_throughput">maximum throughput</option>
                <option value="lowest_p99">lowest P99 latency</option>
              </select>
            </label>
            <label>
              {t("mode")}
              <select name="mode" defaultValue="standard">
                <option value="standard">{t("standardMode")}</option>
                <option value="intelligent">{t("intelligentMode")}</option>
              </select>
              <small>{t("standardModeHint")}</small>
            </label>
            <label>
              {t("frameworkVersion")}
              <input name="framework_version" defaultValue="0.10.0" />
            </label>
            <label>
              {t("promptDataset")}
              <input name="prompt_dataset" defaultValue="random" />
            </label>
            <label>
              {t("tensorParallel")}
              <input name="tensor_parallel_size" type="number" min="1" defaultValue="4" />
            </label>
            <label>
              {t("gpuMemory")}
              <input name="gpu_memory_utilization" type="number" min="0.1" max="1" step="0.01" defaultValue="0.88" />
            </label>
            <label>
              {t("maxSeqs")}
              <input name="max_num_seqs" type="number" min="1" defaultValue="128" />
            </label>
            <label>
              {t("maxTrials")}
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
                <RotateCw size={16} /> {planExperiment.isPending ? t("planning") : t("preview")}
              </button>
              <button className="primary" disabled={!machineId || !modelId || createExperiment.isPending}>
                <TerminalSquare size={16} /> {createExperiment.isPending ? t("creating") : t("create")}
              </button>
            </div>
          </form>
        </div>
        <AgentSettingsPanel />
      </div>
      <form
        className="panel form-grid"
        onSubmit={(event) => {
          event.preventDefault();
          distributeModel.mutate(new FormData(event.currentTarget));
        }}
      >
        <label>
          {t("distributionTarget")}
          <input name="target_path" placeholder="default model cache path" />
        </label>
        <label className="check-row">
          <input
            type="checkbox"
            checked={distributeDryRun}
            onChange={(event) => setDistributeDryRun(event.target.checked)}
          />
          {t("dryRunDistribution")}
        </label>
        <button className="secondary form-action" disabled={!machineId || !modelId || distributeModel.isPending}>
          <HardDrive size={16} /> {distributeModel.isPending ? t("distributing") : t("distributeModel")}
        </button>
        <span className="form-note">
          {distributionResult ? JSON.stringify(distributionResult.result) : "Uses the selected machine and model"}
        </span>
      </form>
      <div className="split">
        <div className="panel">
          <h2>{t("candidatePreview")}</h2>
          <pre>{JSON.stringify(plan ?? experiments[0]?.reproducibility ?? {}, null, 2)}</pre>
        </div>
        <div className="panel table-panel">
          <h2>{t("recentExperiments")}</h2>
          <table>
            <thead>
              <tr>
                <th>{t("name")}</th>
                <th>{t("mode")}</th>
                <th>{t("runtime")}</th>
                <th>{t("status")}</th>
                <th>{t("candidates")}</th>
              </tr>
            </thead>
            <tbody>
              {experiments.slice(0, 5).map((experiment) => (
                <tr key={experiment.id}>
                  <td>{experiment.name}</td>
                  <td>{experiment.mode}</td>
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
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [executionMode, setExecutionMode] = useState<ExecutionMode>("fake");
  const [benchmarkKind, setBenchmarkKind] = useState<BenchmarkKind>("serve");
  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: api.jobs,
    refetchInterval: (query) => {
      const latest = query.state.data?.[0];
      return latest && ["queued", "running"].includes(latest.status) ? 3000 : false;
    }
  });
  const latestJob = jobs.data?.[0] as JobRecord | undefined;
  const latestJobLogs = useQuery({
    queryKey: ["job-logs", latestJob?.id],
    queryFn: () => api.jobLogs(latestJob?.id ?? ""),
    enabled: Boolean(latestJob),
    refetchInterval: latestJob && ["queued", "running"].includes(latestJob.status) ? 3000 : false
  });
  const createBenchmark = useMutation({
    mutationFn: (formData: FormData) => {
      if (!experiment) {
        throw new Error("No experiment selected");
      }
      const runSpec = runSpecFromExperiment(experiment);
      const requestRate = optionalNumberValue(formData.get("request_rate"));
      return api.createBenchmarkJob({
        run_spec: runSpec,
        execution_mode: executionMode,
        benchmark: {
          run_spec: runSpec,
          kind: benchmarkKind,
          dataset_name: String(formData.get("dataset_name") ?? "random"),
          input_len: numberValue(formData.get("input_len"), 1024),
          output_len: numberValue(formData.get("output_len"), 256),
          num_prompts: numberValue(formData.get("num_prompts"), 128),
          request_rate: requestRate,
          result_filename: `${experiment.id}-${benchmarkKind}.json`
        }
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["jobs"] })
  });

  return (
    <section className="stack">
      <header className="page-head">
        <div>
          <h1>{t("experimentRun")}</h1>
          <p>{t("experimentRunDesc")}</p>
          {experiment ? <small>{t("mode")}: {experiment.mode}</small> : null}
        </div>
        {experiment ? <StatusPill status={experiment.status} /> : null}
      </header>
      <div className="split">
        <div className="panel">
          <h2>{t("metrics")}</h2>
          <MetricsChart metrics={metrics} />
        </div>
        <form
          className="panel form-grid"
          onSubmit={(event) => {
            event.preventDefault();
            createBenchmark.mutate(new FormData(event.currentTarget));
          }}
        >
          <label>
            {t("execution")}
            <select value={executionMode} onChange={(event) => setExecutionMode(event.target.value as ExecutionMode)}>
              <option value="fake">fake local</option>
              <option value="remote_inline">real SSH inline</option>
              <option value="remote_rq">real SSH via RQ</option>
            </select>
          </label>
          <label>
            {t("kind")}
            <select value={benchmarkKind} onChange={(event) => setBenchmarkKind(event.target.value as BenchmarkKind)}>
              <option value="serve">serve</option>
              <option value="throughput">throughput</option>
            </select>
          </label>
          <label>
            {t("dataset")}
            <input name="dataset_name" defaultValue="random" />
          </label>
          <label>
            {t("prompts")}
            <input name="num_prompts" type="number" min="1" defaultValue="128" />
          </label>
          <label>
            {t("inputTokens")}
            <input name="input_len" type="number" min="1" defaultValue="1024" />
          </label>
          <label>
            {t("outputTokens")}
            <input name="output_len" type="number" min="1" defaultValue="256" />
          </label>
          <label>
            {t("requestRate")}
            <input name="request_rate" type="number" min="0.1" step="0.1" placeholder="unlimited" />
          </label>
          <button className="primary form-action" disabled={!experiment || createBenchmark.isPending}>
            <Play size={16} /> {createBenchmark.isPending ? t("submitting") : t("runBenchmark")}
          </button>
        </form>
      </div>
      <div className="split">
        <div className="panel">
          <h2>{t("experimentLogs")}</h2>
          <pre>{(runLog?.lines ?? ["No experiment selected"]).join("\n")}</pre>
        </div>
        <div className="panel">
          <h2>{t("jobLogs")}</h2>
          <pre>{(latestJobLogs.data?.logs ?? latestJob?.logs ?? ["No benchmark job selected"]).join("\n")}</pre>
        </div>
      </div>
      <div className="panel table-panel">
        <h2>{t("benchmarkJobs")}</h2>
        <table>
          <thead>
            <tr>
              <th>Job</th>
              <th>{t("status")}</th>
              <th>{t("progress")}</th>
              <th>{t("error")}</th>
            </tr>
          </thead>
          <tbody>
            {(jobs.data ?? []).slice(0, 8).map((job) => (
              <tr key={job.id}>
                <td className="mono">{job.id}</td>
                <td>
                  <StatusPill status={job.status} />
                </td>
                <td>{Math.round(job.progress * 100)}%</td>
                <td>{job.error ?? "none"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="panel table-panel">
        <h2>{t("trials")}</h2>
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>{t("status")}</th>
              <th>{t("params")}</th>
              <th>{t("command")}</th>
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
        <h2>{t("launchCommand")}</h2>
        <code>{experiment?.launch_command ?? "No experiment selected"}</code>
      </div>
    </section>
  );
}

function CompareView({ experiments, metrics }: { experiments: Experiment[]; metrics: MetricsSummary[] }) {
  const { t } = useI18n();
  const container = experiments.find((experiment) => experiment.runtime_mode === "container");
  const bare = experiments.find((experiment) => experiment.runtime_mode === "bare_metal");
  return (
    <section className="stack">
      <header className="page-head">
        <div>
          <h1>Container vs Bare Metal</h1>
          <p>Same machine, model hash, prompts, benchmark version, and parameter space.</p>
          <small>{t("standardMode")} / {t("intelligentMode")}</small>
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
  const { t } = useI18n();
  return (
    <section className="stack">
      <header className="page-head">
        <div>
          <h1>{t("historyTitle")}</h1>
          <p>{t("historyDesc")}</p>
        </div>
      </header>
      <div className="panel table-panel">
        <table>
          <thead>
            <tr>
              <th>{t("name")}</th>
              <th>{t("mode")}</th>
              <th>{t("runtime")}</th>
              <th>{t("framework")}</th>
              <th>{t("promptDataset")}</th>
              <th>{t("status")}</th>
            </tr>
          </thead>
          <tbody>
            {experiments.map((experiment) => (
              <tr key={experiment.id}>
                <td>{experiment.name}</td>
                <td>{experiment.mode}</td>
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
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [downloadResult, setDownloadResult] = useState("");
  const reportMutation = useMutation({
    mutationFn: () => api.generateReport(experiment?.id ?? "experiment-container"),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reports", experiment?.id] })
  });
  const downloadReport = useMutation({
    mutationFn: ({ reportId, format }: { reportId: string; format: "markdown" | "pdf" | "docx" }) =>
      api.downloadReport(reportId, format),
    onSuccess: (result) => setDownloadResult(result.presigned_url || result.uri)
  });
  const reports = useQuery({
    queryKey: ["reports", experiment?.id],
    queryFn: () => api.reports(experiment?.id)
  });
  const artifacts = useQuery({ queryKey: ["artifacts"], queryFn: api.artifacts });

  return (
    <section className="stack">
      <header className="page-head">
        <div>
          <h1>{t("reportTitle")}</h1>
          <p>{t("reportDesc")}</p>
        </div>
        <button className="primary" disabled={!experiment || reportMutation.isPending} onClick={() => reportMutation.mutate()}>
          <FileText size={16} /> {t("generate")}
        </button>
      </header>
      <div className="panel table-panel">
        <table>
          <thead>
            <tr>
              <th>{t("template")}</th>
              <th>{t("status")}</th>
              <th>{t("artifact")}</th>
              <th>{t("download")}</th>
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
                <td>
                  <div className="row-actions">
                    {(["markdown", "pdf", "docx"] as const).map((format) => (
                      <button
                        className="icon-button"
                        key={format}
                        title={`Download ${format}`}
                        onClick={() => downloadReport.mutate({ reportId: report.id, format })}
                      >
                        <Download size={14} />
                      </button>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="panel">
        <h2>{t("downloadResult")}</h2>
        <code>{downloadResult || "No export requested"}</code>
      </div>
      <div className="panel table-panel">
        <h2>{t("artifacts")}</h2>
        <table>
          <thead>
            <tr>
              <th>{t("kind")}</th>
              <th>{t("name")}</th>
              <th>{t("uri")}</th>
              <th>{t("size")}</th>
            </tr>
          </thead>
          <tbody>
            {(artifacts.data ?? []).slice(0, 10).map((artifact) => (
              <tr key={artifact.id}>
                <td>{artifact.kind}</td>
                <td>{artifact.name}</td>
                <td className="mono">{artifact.uri}</td>
                <td>{artifact.size_bytes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function App() {
  const [locale, setLocaleState] = useState<Locale>(() => initialLocale());
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
  const i18n = useMemo(
    () => ({
      locale,
      setLocale: (nextLocale: Locale) => {
        window.localStorage.setItem("inflab-locale", nextLocale);
        setLocaleState(nextLocale);
      },
      t: (key: MessageKey) => translate(locale, key)
    }),
    [locale]
  );

  return (
    <I18nContext.Provider value={i18n}>
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
    </I18nContext.Provider>
  );
}
