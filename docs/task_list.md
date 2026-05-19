# Task List

> 执行顺序：先完成后端全部接口和实现，再开始前端。不得同时推进后端和前端。

## Phase 0: 项目基线

- [ ] 建立 `backend/` Python 项目骨架：`pyproject.toml`、包结构、测试结构。
- [ ] 锁定 Python 3.12+、uv、pytest、ruff 基础命令。
- [ ] 建立最小 `deploy/compose.yaml`：PostgreSQL、Redis、MinIO。
- [ ] 建立后端配置模型：数据库、Redis、对象存储、SSH、LLM provider。
- [ ] 建立统一日志、错误响应、请求 ID、健康检查。
- [ ] 建立后端 CI 本地命令：`uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`。

## Phase 1: 后端 API 与数据模型

- [ ] 建立 FastAPI 应用骨架和 OpenAPI 输出。
- [ ] 建立 SQLAlchemy 2 + Alembic migration。
- [ ] 建立核心数据库表：
  - `machines`
  - `machine_snapshots`
  - `bootstrap_runs`
  - `experiments`
  - `experiment_trials`
  - `metrics_summary`
  - `metrics_samples`
  - `artifacts`
  - `models`
  - `images`
- [ ] 建立通用分页、筛选、排序、错误模型。
- [ ] 建立对象存储 artifact 元数据模型和上传/引用接口。
- [ ] 建立任务队列模型：job 创建、状态查询、日志/进度查询。

## Phase 2: 后端 Remote Executor

- [ ] 定义 executor 抽象：命令执行、文件上传下载、sudo、环境变量、timeout、streaming logs。
- [ ] 定义 `RemoteStep` 协议：`detect` / `apply` / `verify`。
- [ ] 定义 `StepResult`：status、commands、exit_code、stdout/stderr URI、changed_files、snapshots、failure_hint。
- [ ] 实现 fake executor，用于默认单元测试。
- [ ] 实现本地 shell executor，用于开发验证。
- [ ] 实现 AsyncSSH executor。
- [ ] 实现 rsync/scp 文件分发能力。
- [ ] 为 executor 和 step runner 补齐单元测试，不依赖真实 SSH 机器。

## Phase 3: 后端机器纳管与 Bootstrap

- [ ] 实现机器 CRUD API。
- [ ] 实现 SSH 凭据加密存储和脱敏返回。
- [ ] 实现机器探测任务：硬件、系统、容器、GPU、网络、磁盘、拓扑基础信息。
- [ ] 实现机器画像 JSON 和机型指纹。
- [ ] 实现 Bootstrap Profile API：Minimal、Standard Container、Standard Bare-Metal、Full、Custom。
- [ ] 实现 B1 Access Bootstrap。
- [ ] 实现 B2 Source Bootstrap。
- [ ] 实现 B3 Package Bootstrap。
- [ ] 实现 B4 Storage Bootstrap。
- [ ] 实现 B5 Container Bootstrap。
- [ ] 实现 B6 baseline 记录；调优 profile 留到后续版本。
- [ ] 实现 B7 Bare-Metal Runtime Bootstrap。
- [ ] 实现 bootstrap run 查询、模块状态、失败分类、重跑单模块接口。

## Phase 4: 后端插件与运行时

- [ ] 定义 `RuntimePlugin` 协议，显式支持 `container` 和 `bare_metal`。
- [ ] 定义 `FrameworkPlugin` 协议。
- [ ] 定义 `DriverPlugin` 协议。
- [ ] 定义 `ModelPlugin` 协议。
- [ ] 实现插件注册表，不做热加载。
- [ ] 实现 container runtime plugin。
- [ ] 实现 bare-metal runtime plugin。
- [ ] 实现 NVIDIA driver/runtime 基础探测。
- [ ] 实现 vLLM framework plugin：container 路径。
- [ ] 实现 vLLM framework plugin：bare-metal 路径。
- [ ] 实现 SGLang framework plugin：container 路径。
- [ ] 实现 SGLang framework plugin：bare-metal 路径。
- [ ] 为插件 contract 建立 fake plugin 测试。

## Phase 5: 后端模型分发与制品管理

- [ ] 实现模型 registry API：模型名称、来源、格式、hash、缓存路径。
- [ ] 实现 rsync 模型分发。
- [ ] 实现 NFS/MinIO 引用模式。
- [ ] 实现 HuggingFace/ModelScope 下载适配接口，MVP 可先 mock 或 opt-in。
- [ ] 实现 SHA256 校验。
- [ ] 实现断点续传策略。
- [ ] 实现镜像 manifest/digest 入库。
- [ ] 实现报告、日志、快照、原始 metrics artifact 管理。

## Phase 6: 后端 Benchmark Runner

- [ ] 定义统一 `RunSpec`。
- [ ] 定义统一 `BenchmarkResult`。
- [ ] 实现 benchmark job 创建和状态查询 API。
- [ ] 实现 vLLM benchmark 适配。
- [ ] 实现 SGLang benchmark 适配。
- [ ] 实现 TTFT、TPOT、P50/P90/P99、吞吐、失败率归一化。
- [ ] 实现 GPU/CPU/显存/功耗采集接口。
- [ ] 实现原始日志和原始 metrics 归档。
- [ ] 实现容器 vs 裸机公平对比校验：同机器、同模型 hash、同 prompt、同 benchmark version。

## Phase 7: 后端 Agent 调参与实验编排

- [ ] 定义实验 API：创建、查询、取消、复制、对比。
- [ ] 定义 trial API：参数组合、启动命令、结果、失败分类。
- [ ] 实现 Agent 状态机：Observe、Plan、Validate、Act、Collect、Reflect。
- [ ] 实现规则 baseline。
- [ ] 实现 Grid Search。
- [ ] 实现 Random Search。
- [ ] 实现 LLM candidate provider adapter。
- [ ] 实现 Pydantic schema 校验和启发式剪枝。
- [ ] 实现预算控制：最大轮数、最长时间、功耗预算。
- [ ] 实现失败分类：OOM、驱动错误、配置错误、性能不达标、超时、其他。
- [ ] 实现实验可复现字段完整入库。

## Phase 8: 后端报告生成

- [ ] 定义报告模板模型：内部研发、客户交付、性能白皮书。
- [ ] 实现 Markdown 报告渲染。
- [ ] 实现 PDF 生成。
- [ ] 实现 DOCX 生成。
- [ ] 实现图表数据导出接口。
- [ ] 实现报告 artifact 入库。
- [ ] 实现报告脱敏策略：密钥、token、内网地址、NAS 路径。
- [ ] 实现报告 API：生成、查询、下载、重新生成。

## Phase 9: 后端验收门禁

前端工作只有在本阶段全部完成后才能开始。

- [ ] 所有后端 API 有 OpenAPI schema。
- [ ] 所有数据库 migration 可从空库执行成功。
- [ ] 默认测试不依赖真实 SSH、GPU、NAS、Docker daemon mutation、外部 LLM。
- [ ] `uv run pytest` 通过。
- [ ] `uv run ruff check .` 通过。
- [ ] `uv run ruff format --check .` 通过。
- [ ] Docker Compose 可启动后端依赖服务。
- [ ] 使用 fake executor 跑通机器纳管、bootstrap、benchmark、experiment、report 的最小闭环。
- [ ] 后端接口文档更新完成。
- [ ] `AGENTS.md` 中的后端约束与实际实现一致。

## Phase 10: 前端

只有 Phase 9 完成后才能开始。

- [ ] 建立 `frontend/` React + Vite + TypeScript 项目。
- [ ] 建立 API typed client。
- [ ] 建立基础布局和导航。
- [ ] 实现机器列表、机器详情、新增机器。
- [ ] 实现 Bootstrap profile 选择和执行进度。
- [ ] 实现实验创建页。
- [ ] 实现实验运行页：日志、trial、指标。
- [ ] 实现容器 vs 裸机对比视图。
- [ ] 实现历史实验对比。
- [ ] 实现报告生成和下载。
- [ ] 实现前端测试、lint、build。

## Working Rule

- 当前阶段只做后端相关任务和文档维护。
- 不创建 `frontend/`，不安装前端依赖，不实现前端页面，直到 Phase 9 完成。
- 如果后端任务需要前端字段，先通过 OpenAPI schema、示例 JSON、接口文档表达，不提前写 UI。
