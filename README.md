# InferenceLab / ModelBench Agent

面向 AI 整机厂商的自动化模型推理测试、调优与报告平台。

当前仓库处于需求与技术选型阶段，核心文档：

- [需求设计文档](modelbench_agent_requirements_2.md)
- [技术选型文档](modelbench_agent_tech_selection.md)
- [Agent Harness](docs/agent_harness.md)

## Agent Harness

本仓库使用 `AGENTS.md` 作为 Codex / 编码 Agent 的项目操作手册。

## MVP 技术方向

- Backend: FastAPI + PostgreSQL + Redis/RQ
- Remote Executor: AsyncSSH + rsync + 幂等 Step
- Frontend: React + Vite + TypeScript + ECharts
- Reports: Markdown + Pandoc + Typst
- Deployment: Docker Compose 单实例
