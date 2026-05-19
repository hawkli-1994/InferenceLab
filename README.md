# InferenceLab / ModelBench Agent

面向 AI 整机厂商的自动化模型推理测试、调优与报告平台。

当前仓库包含一个 workshop-grade MVP 实现：FastAPI 后端、SQLAlchemy/Alembic
数据模型、fake executor / fake plugin 业务闭环，以及 React + Vite 工作台前端。

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

前端工作台：

```bash
cd frontend
pnpm install
pnpm dev
pnpm build
```

## E2E Status

本轮实现按任务要求刻意绕过真实 GitHub Actions E2E：没有提交
`tests/e2e/backend_e2e_enabled`，也没有启用 Ubuntu target container E2E。质量保障来自
后端单元/API contract/fake executor 测试和前端 `pnpm build`。
