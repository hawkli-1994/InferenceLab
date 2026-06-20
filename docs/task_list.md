# Task List

> 执行顺序：先完成后端全部接口和实现，再开始前端。不得同时推进后端和前端。

## Phase 0: 项目基线

- [x] 建立 `backend/` Python 项目骨架：`pyproject.toml`、包结构、测试结构。
- [x] 锁定 Python 3.12+、uv、pytest、ruff 基础命令。
- [x] 建立最小 `deploy/compose.yaml`：PostgreSQL、Redis、MinIO。
- [x] 建立后端配置模型：数据库、Redis、对象存储、SSH、LLM provider。
- [x] 建立统一日志、错误响应、请求 ID、健康检查。
- [x] 建立后端 CI 本地命令：`uv run pytest`、`uv run ruff check .`、`uv run ruff format --check .`。

## Phase 1: 后端 API 与数据模型

- [x] 建立 FastAPI 应用骨架和 OpenAPI 输出。
- [x] 建立 SQLAlchemy 2 + Alembic migration。
- [x] 建立核心数据库表：
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
- [x] 建立通用分页、筛选、排序、错误模型。
- [x] 建立对象存储 artifact 元数据模型和上传/引用接口。
- [x] 建立任务队列模型：job 创建、状态查询、日志/进度查询。

## Phase 2: 后端 Remote Executor

- [x] 定义 executor 抽象：命令执行、文件上传下载、sudo、环境变量、timeout、streaming logs。
- [x] 定义 `RemoteStep` 协议：`detect` / `apply` / `verify`。
- [x] 定义 `StepResult`：status、commands、exit_code、stdout/stderr URI、changed_files、snapshots、failure_hint。
- [x] 实现 fake executor，用于默认单元测试。
- [x] 实现本地 shell executor，用于开发验证。
- [x] 实现 AsyncSSH executor。
- [x] 实现 rsync/scp 文件分发能力。
- [x] 为 executor 和 step runner 补齐单元测试，不依赖真实 SSH 机器。

## Phase 3: 后端机器纳管与 Bootstrap

- [x] 实现机器 CRUD API。
- [x] 实现 SSH 凭据加密存储和脱敏返回。
- [x] 实现机器探测任务：硬件、系统、容器、GPU、网络、磁盘、拓扑基础信息。
- [x] 实现机器画像 JSON 和机型指纹。
- [x] 实现 Bootstrap Profile API：Minimal、Standard Container、Standard Bare-Metal、Full、Custom。
- [x] 实现 B1 Access Bootstrap。
- [x] 实现 B2 Source Bootstrap。
- [x] 实现 B3 Package Bootstrap。
- [x] 实现 B4 Storage Bootstrap。
- [x] 实现 B5 Container Bootstrap。
- [x] 实现 B6 baseline 记录；调优 profile 留到后续版本。
- [x] 实现 B7 Bare-Metal Runtime Bootstrap。
- [x] 实现 bootstrap run 查询、模块状态、失败分类、重跑单模块接口。

## Phase 4: 后端插件与运行时

- [x] 定义 `RuntimePlugin` 协议，显式支持 `container` 和 `bare_metal`。
- [x] 定义 `FrameworkPlugin` 协议。
- [x] 定义 `DriverPlugin` 协议。
- [x] 定义 `ModelPlugin` 协议。
- [x] 实现插件注册表，不做热加载。
- [x] 实现 container runtime plugin。
- [x] 实现 bare-metal runtime plugin。
- [x] 实现 NVIDIA driver/runtime 基础探测。
- [x] 实现 vLLM framework plugin：container 路径。
- [x] 实现 vLLM framework plugin：bare-metal 路径。
- [x] 实现 SGLang framework plugin：container 路径。
- [x] 实现 SGLang framework plugin：bare-metal 路径。
- [x] 为插件 contract 建立 fake plugin 测试。

## Phase 5: 后端模型分发与制品管理

- [x] 实现模型 registry API：模型名称、来源、格式、hash、缓存路径。
- [x] 实现 rsync 模型分发。
- [x] 实现 NFS/MinIO 引用模式。
- [x] 实现 HuggingFace/ModelScope 下载适配接口，MVP 可先 mock 或 opt-in。
- [x] 实现 SHA256 校验。
- [x] 实现断点续传策略。
- [x] 实现镜像 manifest/digest 入库。
- [x] 实现报告、日志、快照、原始 metrics artifact 管理。

## Phase 6: 后端 Benchmark Runner

- [x] 定义统一 `RunSpec`。
- [x] 定义统一 `BenchmarkResult`。
- [x] 实现 benchmark job 创建和状态查询 API。
- [x] 实现 vLLM benchmark 适配。
- [x] 实现 SGLang benchmark 适配。
- [x] 实现 TTFT、TPOT、P50/P90/P99、吞吐、失败率归一化。
- [x] 实现 GPU/CPU/显存/功耗采集接口。
- [x] 实现原始日志和原始 metrics 归档。
- [x] 实现容器 vs 裸机公平对比校验：同机器、同模型 hash、同 prompt、同 benchmark version。

## Phase 7: 后端 Agent 调参与实验编排

- [x] 定义实验 API：创建、查询、取消、复制、对比。
- [x] 定义 trial API：参数组合、启动命令、结果、失败分类。
- [x] 实现 Agent 状态机：Observe、Plan、Validate、Act、Collect、Reflect。
- [x] 实现规则 baseline。
- [x] 实现 Grid Search。
- [x] 实现 Random Search。
- [x] 实现 LLM candidate provider adapter。
- [x] 实现 Pydantic schema 校验和启发式剪枝。
- [x] 实现预算控制：最大轮数、最长时间、功耗预算。
- [x] 实现失败分类：OOM、驱动错误、配置错误、性能不达标、超时、其他。
- [x] 实现实验可复现字段完整入库。

## Phase 8: 后端报告生成

- [x] 定义报告模板模型：内部研发、客户交付、性能白皮书。
- [x] 实现 Markdown 报告渲染。
- [x] 实现 PDF 生成。
- [x] 实现 DOCX 生成。
- [x] 实现图表数据导出接口。
- [x] 实现报告 artifact 入库。
- [x] 实现报告脱敏策略：密钥、token、内网地址、NAS 路径。
- [x] 实现报告 API：生成、查询、下载、重新生成。

## Phase 9: 后端验收门禁

本轮按用户明确要求刻意绕过真实 E2E，因此未提交 marker、未启用 GitHub Actions 强制 E2E。

- [x] 所有后端 API 有 OpenAPI schema。
- [x] 所有数据库 migration 可从空库执行成功。
- [x] 默认测试不依赖真实 SSH、GPU、NAS、Docker daemon mutation、外部 LLM。
- [ ] 实现 `tests/e2e/images/ubuntu-target/Dockerfile`。
- [ ] 实现 `tests/e2e/test_control_plane_fake_executor.py`。
- [ ] 实现 `tests/e2e/test_bootstrap_ubuntu_target.py`。
- [ ] 实现 `scripts/ci/wait-for-ssh.sh`。
- [ ] 固定 GitHub Actions E2E 依赖镜像版本，避免使用浮动 `latest`。
- [ ] 提交 `tests/e2e/backend_e2e_enabled`，启用 GitHub Actions `Backend E2E` workflow。
- [ ] GitHub Actions `Backend E2E` workflow 通过。
- [x] `uv run pytest` 通过。
- [x] `uv run ruff check .` 通过。
- [x] `uv run ruff format --check .` 通过。
- [x] Docker Compose 定义包含 backend API、RQ worker、frontend、PostgreSQL、Redis、MinIO
  和 bucket init。
- [x] 使用 fake executor 跑通机器纳管、bootstrap、benchmark、experiment、report 的最小闭环。
- [x] 后端接口文档更新完成。
- [x] `AGENTS.md` 中的后端约束与实际实现一致。

## Phase 10: 前端

本轮前端是在用户明确要求绕过 Phase 9 E2E 后启动。

- [x] 建立 `frontend/` React + Vite + TypeScript 项目。
- [x] 建立 API typed client。
- [x] 建立基础布局和导航。
- [x] 实现机器列表、机器详情、新增机器。
- [x] 实现 Bootstrap profile 选择和执行进度。
- [x] 实现实验创建页。
- [x] 实现实验运行页：日志、trial、指标。
- [x] 实现容器 vs 裸机对比视图。
- [x] 实现历史实验对比。
- [x] 实现报告生成和下载。
- [x] 实现前端测试、lint、build（本轮未配置 test/lint，`pnpm build` 通过）。

## Forward Development While E2E/CI Is Bypassed

继续按用户要求绕过真实 E2E 和 CI gate；本节记录默认测试不依赖真实 SSH/GPU/Docker
mutation 的功能推进。真实 SSH 路径可以手动 opt-in，但不作为默认测试前提。

- [x] 实现真实 AsyncSSH executor：password/private key、host key policy、cwd/env/sudo/timeout、SFTP upload/download。
- [x] 将 `POST /api/v1/machines/{machine_id}/bootstrap` 的 `dry_run=false` 接入真实 AsyncSSH executor。
- [x] 为真实 SSH executor 增加 mock AsyncSSH 单元测试，不依赖真实机器。
- [x] 新增实验候选预览 API：`POST /api/v1/experiments/plan`。
- [x] 新增 vLLM/SGLang benchmark command-plan API：`POST /api/v1/benchmarks/plan`。
- [x] 新增真实 benchmark opt-in 执行：`execution_mode=remote_inline` 通过 AsyncSSH 运行，
  `execution_mode=remote_rq` 通过 Redis/RQ worker 调度。
- [x] 新增真实机器探测 opt-in：`POST /api/v1/machines/{machine_id}/probe?dry_run=false`。
- [x] 新增模型分发 opt-in：rsync、NFS、MinIO、HuggingFace、ModelScope 命令路径。
- [x] 新增 S3/MinIO artifact 上传实现和测试。
- [x] 远程 benchmark 日志和 raw result 以 best-effort 方式上传 artifact。
- [x] 新增 Pandoc/Typst 报告导出路径；工具链不可用时返回 503。
- [x] 使用 LiteLLM 实现 OpenAI-compatible/Anthropic LLM candidate provider adapter。
- [x] 将 AsyncSSH executor 的 benchmark 日志改为 process stdout/stderr 流式读取。
- [x] 创建实验时记录 Agent phase、candidate count、experiment job、trial 日志。
- [x] 新增实验运行日志聚合 API：`GET /api/v1/experiments/{experiment_id}/run-log`。
- [x] 新增报告列表 API：`GET /api/v1/reports`，支持按 `experiment_id` 过滤。
- [x] 新增数据库 demo seed：`POST /api/v1/dev/seed-demo-data` 和 `INFLAB_SEED_DEMO_DATA=true`。
- [x] 前端机器表单接入真实新增机器、dry-run/SSH 探测 API。
- [x] 前端 Bootstrap 页面接入 dry-run/SSH 执行和结构化 step 输出。
- [x] 前端实验创建页接入数据库模型注册、模型分发、候选预览、实验创建。
- [x] 前端 Run 页面展示真实 trial、run-log、metrics，并可提交 fake/remote inline/remote RQ benchmark job。
- [x] 前端 Run 页面轮询 job logs/progress。
- [x] 前端 Report 页面读取真实报告列表、触发生成、请求导出、展示 artifacts。
- [x] 删除前端本地 mock fallback；前端只通过后端 API 读取数据库数据。
- [x] 引入实验 `mode=standard|intelligent`，默认标准模式。
- [x] 标准模式使用软件驱动 deterministic matrix，参考 `llm_test_tools` 的 progressive case 设计。
- [x] 智能模式保留 Agent/LLM candidate path，并为 Deli_AutoResearch 协议集成留边界。
- [x] 新增 `GET /api/v1/autoresearch/integration-plan`，记录 Deli_AutoResearch 的状态文件、watchdog、gates 和适用范围。
- [x] 前端实验创建页支持标准模式/智能模式切换。
- [x] 前端增加中文/英文 i18n 字典和语言切换。
- [ ] 将报告模板扩展为中文/英文双语输出。
- [ ] 将标准模式的 progressive skip 状态写入 trial/result，而不仅是候选矩阵。
- [ ] 产品化 Deli_AutoResearch 智能模式：接入 state files、stall detection、forced pivot、heartbeat watchdog 和运行记录。

## Working Rule

- 默认阶段顺序仍是先后端、后前端。
- 不创建 `frontend/`，不安装前端依赖，不实现前端页面，直到 Phase 9 完成；本轮是用户明确要求绕过真实 E2E 的例外。
- 如果后端任务需要前端字段，先通过 OpenAPI schema、示例 JSON、接口文档表达，不提前写 UI。
