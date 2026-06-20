# Execution Modes, i18n, and Deli_AutoResearch

> 更新日期：2026-06-20  
> 背景：在 Agent 调度测试成熟之前，先交付软件驱动的标准模式；后续保留标准模式和智能模式双模式切换。

## 1. 双模式定义

| 模式 | 英文名 | 定位 | 默认启用 |
|---|---|---|---|
| 标准模式 | `standard` | 软件驱动、确定性 case 矩阵、可解释、可复现 | 是 |
| 智能模式 | `intelligent` | Deli_AutoResearch 协议 + Pi agent 执行器驱动的长周期优化 | 否 |

### 标准模式

标准模式参考 `/Users/krli/workspace/llm_test_tools`：

- 通过脚本/规则生成 case 矩阵，不依赖 LLM 决策。
- `parallel_size` 和 `num_prompts` 可一一配对，避免无意义的笛卡尔爆炸。
- 输入/输出长度使用少量代表点，例如 `512/512`、`2048/2048`、`16384/16384`、`50000/50000`。
- 按上下文从短到长执行，先跑低风险 case。
- 启动阶段 OOM 后跳过更大上下文，减少浪费。
- 输出公司可读报告，保留原始日志和 summary。

标准模式是当前默认模式，因为它更容易验收，也更符合内部工具的“可解释、可复现、先跑通”目标。

### 智能模式

智能模式在标准模式稳定后启用，包含：

- 当前已有 Agent 状态机：Observe、Plan、Validate、Act、Collect、Reflect。
- LLM candidate provider。
- Deli_AutoResearch 协议：状态文件、停滞检测、强制 pivot、heartbeat watchdog、guardian/worker 分离。
- Pi agent worker executor：执行单轮有界 worker iteration。
- gates：单元测试、API contract、前端 build、benchmark score floor。

智能模式不能绕开标准模式的数据结构。所有 trial 仍必须记录：

- machine profile
- model hash
- runtime mode
- framework version
- framework params
- prompt dataset
- launch command
- experiment mode

## 2. API 约定

实验创建和候选预览都带 `mode`：

```json
{
  "name": "container baseline",
  "mode": "standard",
  "goal": "max_throughput",
  "budget": {"max_trials": 8},
  "run_spec": {
    "machine_id": "...",
    "model_id": "...",
    "runtime_mode": "container",
    "framework": "vllm"
  }
}
```

后端默认：

- 未传 `mode` 时使用 `standard`。
- `standard` 只使用确定性矩阵规划。
- `intelligent` 才允许调用 LLM candidate provider 和 Deli_AutoResearch orchestration。

智能模式协议计划通过以下接口暴露：

```text
GET /api/v1/autoresearch/integration-plan
GET /api/v1/agent-executors/pi/plan
GET /api/v1/agent-executors/pi/prompt
GET /api/v1/agent-settings
PUT /api/v1/agent-settings
POST /api/v1/agent-settings/validate
```

## 3. Deli_AutoResearch 选型

引入 `Deli_AutoResearch` skill 作为智能模式协议栈。

定位：

- 它不是可执行 benchmark runner，也不是外部 CLI。
- 它是长周期自治任务协议，用来约束智能模式的状态持久化、停滞检测、方向多样性和 watchdog。
- Pi agent 是执行器，不是协议层；它只负责完成一轮 worker iteration。
- InferenceLab 仍保留自己的机器纳管、实验记录、报告和可复现数据模型。

核心协议：

- zero interaction：智能模式运行中不等待人工确认。
- state files：所有长周期状态落到文件，不依赖对话上下文。
- fresh session per iteration：每轮注入 curated state，不使用无限 resume。
- stall detection：0 新发现或指标下降增加 stale count。
- forced pivot：停滞后改变结构性约束，而不是继续调小参数。
- heartbeat watchdog：独立层检查 last_seen、重启/nudge stalled loops。
- guardian/worker separation：守护层只做 liveness-check、restart、nudge。

集成策略：

1. 标准模式不依赖 Deli_AutoResearch。
2. 智能模式先通过后端 `GET /api/v1/autoresearch/integration-plan` 暴露协议、gates 和边界。
3. Pi agent 通过 `GET /api/v1/agent-executors/pi/plan` 暴露可配置执行器计划，通过 `GET /api/v1/agent-executors/pi/prompt` 生成单轮 worker prompt。
4. Agent Settings 面板持久化 LLM provider、Base URL、Model、加密 API Key，以及 Pi agent command/work dir/round/timeout；标准模式不读取这些配置。
5. 后续智能模式落地时，在实验目录生成：
   - `state/task_spec.md`
   - `state/progress.json`
   - `state/findings.jsonl`
   - `state/directions_tried.json`
   - `state/iteration_log.jsonl`
   - `logs/work.jsonl`
   - `logs/orchestrator.jsonl`
   - `logs/heartbeat.jsonl`
6. 每次 Pi worker session 上限来自 Agent Settings，默认 15 rounds 或 30 minutes。
7. 智能模式每轮必须运行 gates：`uv run pytest`、`uv run ruff check .`、`pnpm build`，后续再增加 benchmark score gate。
8. Deli_AutoResearch 只能约束智能模式的编排和搜索；Pi agent 只能执行有界 worker iteration；两者都不得修改实验记录、报告真实性和标准模式行为。

## 4. 国际化策略

前端必须支持中文和英文：

- 默认根据浏览器语言选择 `zh` 或 `en`。
- 用户可在侧边栏切换语言。
- 语言选择写入 `localStorage`。
- 新增 UI 文案必须进入 `frontend/src/i18n.ts`，不能散落硬编码。

后端策略：

- API 字段名保持英文，便于 OpenAPI 和外部系统集成。
- 错误类型、status、mode 等枚举保持英文。
- 面向用户的报告模板和前端文案支持中英文。
- 后续报告生成要增加 locale 参数，默认继承前端选择。

## 5. 实施顺序

1. 标准模式作为默认模式上线。
2. 完善标准模式的 benchmark case matrix、progressive skip 和公司 CSV 报告。
3. 完成 UI/报告国际化。
4. 增加智能模式开关，但默认关闭。
5. 接入 Pi agent 作为智能模式 worker executor。
6. 接入 Deli_AutoResearch 的状态文件、停滞检测和 heartbeat watchdog。
7. 智能模式稳定后，允许用户在标准模式和智能模式之间切换。

## 6. 验收要求

- 新建实验默认 `mode=standard`。
- 候选预览在标准模式下返回 `StandardMatrix` phase。
- 智能模式不会在未配置 LLM/AutoResearch orchestration 时破坏标准流程。
- Pi agent executor plan 明确显示其 worker 角色、命令、工作目录和 round/time cap。
- Agent Settings UI 可配置 LLM provider 和 Pi agent，并明确提示只有智能模式使用。
- UI 可在中文/英文之间切换。
- 单元测试覆盖标准模式矩阵、智能模式规划和 AutoResearch integration plan。
- E2E 仍按当前项目策略绕过，不提交 `tests/e2e/backend_e2e_enabled`。
