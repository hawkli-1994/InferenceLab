# InferenceLab / ModelBench Agent

面向 AI 整机厂商的自动化模型推理测试、调优与报告平台。

当前仓库包含一个 workshop-grade MVP 实现：FastAPI 后端、SQLAlchemy/Alembic
数据模型、AsyncSSH opt-in 远程执行、vLLM/SGLang benchmark command runner、
S3/MinIO artifact 上传、LiteLLM 调参候选 provider、数据库 demo seed，以及 React + Vite
工作台前端。
当前继续按任务要求绕过真实 E2E/CI gate。默认测试仍走安全 fake/dry-run 路径，真实
SSH、远程 benchmark、对象存储和外部 LLM 都需要显式 opt-in。

核心文档：

- [需求设计文档](modelbench_agent_requirements_2.md)
- [技术选型文档](modelbench_agent_tech_selection.md)
- [任务清单](docs/task_list.md)
- [后端 E2E 验收方案](docs/e2e_acceptance.md)
- [双模式、国际化与 AutoResearch 方案](docs/modes_i18n_autoresearch.md)
- [Agent Harness](docs/agent_harness.md)

## Agent Harness

本仓库使用 `AGENTS.md` 作为 Codex / 编码 Agent 的项目操作手册。

## MVP 技术方向

- Backend: FastAPI + PostgreSQL + Redis/RQ
- Remote Executor: AsyncSSH + rsync + 幂等 Step
- Frontend: React + Vite + TypeScript + ECharts
- Modes: 标准模式（默认）+ 智能模式（Deli_AutoResearch + Pi agent）
- i18n: 中文 + English
- Reports: Markdown + Pandoc + Typst
- Deployment: Docker Compose 单实例

## Local Setup

后端默认测试不依赖真实 SSH、GPU、NAS、Docker daemon mutation、外部 LLM 或真实模型下载。

安装后端、前端和 PM2 依赖：

```bash
make install
```

该 target 会运行 `uv sync --all-extras --dev`、`pnpm install`，并在本机没有 PM2 时执行
`npm install -g pm2`。如果不希望修改全局 Node 环境，可以分别运行
`make install-backend` 和 `make install-frontend`，手动安装 PM2。

常用质量检查：

```bash
make test
make lint
make format-check
make frontend-build
```

Docker Compose 单机栈：

```bash
docker compose -f deploy/compose.yaml up --build
```

该栈包含 backend API、RQ worker、frontend、PostgreSQL、Redis、MinIO，并初始化
`inflab-artifacts` bucket。前端默认在 `http://127.0.0.1:8080`，API 在
`http://127.0.0.1:8000`。

后端开发服务：

```bash
cd backend
uv run uvicorn inflab.api.app:app --reload
```

环境接管默认推荐 `Pi 工作流`：用户用泛描述目标说明要达成的环境状态，由 Pi agent
按 discover/plan/apply/verify/record 流程执行。默认 `dry_run=true` 只记录 workflow
prompt、Pi executor plan 和审计结果；取消 dry-run 后才会把 prompt 交给配置好的 Pi
command 执行。该路径不再假设一个固定 Ubuntu 脚本可以覆盖 CUDA、驱动、容器 runtime、
镜像源、NAS、权限等真实分叉。

固定脚本仍作为 `Scripted Baseline` 保留。真实 SSH scripted bootstrap 是手动 opt-in
路径：先创建带凭据的 machine，然后显式传 `strategy=scripted` 和 `dry_run=false`。

```bash
curl -X POST http://127.0.0.1:8000/api/v1/machines/{machine_id}/bootstrap \
  -H 'content-type: application/json' \
  -d '{"profile":"minimal","strategy":"scripted","dry_run":false}'
```

该路径使用 AsyncSSH 连接目标机，支持 password/private key/显式 `ssh_agent`、sudo
command、timeout、远端 cwd/env、SFTP upload/download，以及 benchmark stdout/stderr
流式读取。默认测试和 demo seed 仍不打开真实 SSH 连接。

真实 SSH 只读 smoke 可通过环境变量手动运行：

```bash
INFLAB_REAL_SSH_TARGET=rx@172.18.1.239 uv run pytest backend/tests/test_real_ssh_opt_in.py
```

该 smoke 只执行 `id -un && hostname && uname -srm`，不会写文件、上传数据、sudo 或修改机器配置。

旧的 `manual_environment` 旁路已移除。环境状态必须由 Pi workflow 的执行记录或显式
scripted baseline 结果支撑，避免把未经验证的人工声明误标为 `ready`。

使用数据库 demo 数据启动后端：

```bash
cd backend
INFLAB_DATABASE_URL=sqlite+pysqlite:////tmp/inflab-demo.db \
INFLAB_DATABASE_CREATE_SCHEMA_ON_STARTUP=true \
INFLAB_SEED_DEMO_DATA=true \
uv run uvicorn inflab.api.app:app --reload
```

前端工作台：

```bash
cd frontend
pnpm install
pnpm dev
pnpm build
```

当前前端只调用后端 API，不再导入本地 mock 数据。可直接操作数据库记录：新增机器、
机器探测（dry-run 或真实 SSH）、Pi workflow/scripted 环境接管、注册/分发模型、
预览调参候选、创建实验、提交 benchmark job（fake、remote inline、remote RQ）、
轮询 job logs、查看 trial/log/metrics，并生成/导出报告 artifact 记录。空库可在页面点击
`Seed DB`，或调用
`POST /api/v1/dev/seed-demo-data`。
如果后端不在默认 `http://127.0.0.1:8000`，可用 `VITE_API_BASE` 指向目标 API：

```bash
VITE_API_BASE=http://127.0.0.1:18000/api/v1 pnpm dev -- --port 5174
```

PM2 本地开发进程：

```bash
make pm2-start
make status
make logs-api
make logs-ui
make pm2-stop
```

`make pm2-start` 默认只启动 `inflab-api` 和 `inflab-frontend`。API 使用
`http://127.0.0.1:8000`，Vite 前端使用 `http://127.0.0.1:5173`。PM2 配置位于
`deploy/pm2/ecosystem.config.cjs`，默认使用 `backend/inflab-dev.db` SQLite、本地 schema
auto-create、demo seed 和同步队列，适合快速开发。

需要 Redis/RQ worker 时先启动 Redis，再运行：

```bash
make pm2-worker
# or start API, frontend, and worker together
make pm2-start-all
```

可通过 `INFLAB_DATABASE_URL`、`INFLAB_REDIS_URL`、`INFLAB_REDIS_JOB_MODE`、
`INFLAB_API_PORT`、`INFLAB_UI_PORT`、`VITE_API_BASE` 等环境变量覆盖 PM2 默认值。

真实推理仍不默认执行，但后端已有 vLLM/SGLang benchmark command-plan 和 opt-in
远程执行路径：

- `POST /api/v1/benchmarks/plan`：生成 vLLM/SGLang benchmark 命令和结果路径；
- `POST /api/v1/benchmarks/jobs` with `execution_mode=remote_inline`：通过 AsyncSSH
  直接运行；
- `POST /api/v1/benchmarks/jobs` with `execution_mode=remote_rq`：通过 Redis/RQ worker
  调度运行。

外部 LLM candidate provider 使用 LiteLLM。默认 `INFLAB_LLM_PROVIDER=disabled`；也可在
实验创建页右侧的 `Agent Settings` 面板动态配置 OpenAI-compatible / Anthropic provider、
Base URL、Model、API Key，以及 Pi agent command/work dir/round/timeout。UI 保存的配置会
持久化到数据库并覆盖环境变量默认值；API Key 加密保存且不回显。LLM 配置只影响智能候选；
Pi 配置会用于环境接管 workflow 和后续智能模式 worker。标准模式矩阵规划不依赖这些配置。
候选参数仍会先经过 Pydantic schema 校验和启发式剪枝。

## E2E Status

本轮实现按任务要求刻意绕过真实 GitHub Actions E2E：没有提交
`tests/e2e/backend_e2e_enabled`，也没有启用 Ubuntu target container E2E。质量保障来自
后端单元/API contract/fake executor 测试和前端 `pnpm build`。
