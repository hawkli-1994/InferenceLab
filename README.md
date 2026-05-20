# InferenceLab / ModelBench Agent

面向 AI 整机厂商的自动化模型推理测试、调优与报告平台。

当前仓库包含一个 workshop-grade MVP 实现：FastAPI 后端、SQLAlchemy/Alembic
数据模型、fake executor / fake plugin 业务闭环、数据库 demo seed，以及 React + Vite
工作台前端。
当前继续按任务要求绕过真实 E2E/CI gate，优先推进本地 fake-backed 功能闭环。

核心文档：

- [需求设计文档](modelbench_agent_requirements_2.md)
- [技术选型文档](modelbench_agent_tech_selection.md)
- [任务清单](docs/task_list.md)
- [后端 E2E 验收方案](docs/e2e_acceptance.md)
- [Agent Harness](docs/agent_harness.md)

## Agent Harness

本仓库使用 `AGENTS.md` 作为 Codex / 编码 Agent 的项目操作手册。

## MVP 技术方向

- Backend: FastAPI + PostgreSQL + Redis/RQ
- Remote Executor: AsyncSSH + rsync + 幂等 Step
- Frontend: React + Vite + TypeScript + ECharts
- Reports: Markdown + Pandoc + Typst
- Deployment: Docker Compose 单实例

## Local Setup

后端默认测试不依赖真实 SSH、GPU、NAS、Docker daemon mutation、外部 LLM 或真实模型下载。

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

本地依赖服务：

```bash
docker compose -f deploy/compose.yaml up -d
```

后端开发服务：

```bash
cd backend
uv run uvicorn inflab.api.app:app --reload
```

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
机器探测、dry-run bootstrap、注册 demo 模型、预览调参候选、创建实验、查看
trial/log/metrics，并生成报告 artifact 记录。空库可在页面点击 `Seed DB`，或调用
`POST /api/v1/dev/seed-demo-data`。
如果后端不在默认 `http://127.0.0.1:8000`，可用 `VITE_API_BASE` 指向目标 API：

```bash
VITE_API_BASE=http://127.0.0.1:18000/api/v1 pnpm dev -- --port 5174
```

真实推理仍不默认执行，但后端已有 vLLM benchmark command-plan 接口：
`POST /api/v1/benchmarks/plan`。它生成 `vllm bench serve` / `vllm bench throughput`
命令和结果路径，供后续接入真实远程执行器。

## E2E Status

本轮实现按任务要求刻意绕过真实 GitHub Actions E2E：没有提交
`tests/e2e/backend_e2e_enabled`，也没有启用 Ubuntu target container E2E。质量保障来自
后端单元/API contract/fake executor 测试和前端 `pnpm build`。
