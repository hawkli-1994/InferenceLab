# Backend E2E Acceptance

> 目标：后端全部接口和实现完成后，用 GitHub Actions 自动验证“从一台干净 Ubuntu 目标机到可测试基线”的最小闭环。前端必须等本验收通过后才能开始。

## 1. 验收结论标准

Phase 9 后端验收必须同时满足：

- GitHub Actions `Backend E2E` workflow 通过。
- Fake executor E2E 跑通完整业务闭环。
- Ubuntu target container E2E 跑通安全的 bootstrap 子集。
- 所有测试默认不需要真实 GPU、真实 NAS、内网 registry、外部 LLM、真实客户机器。
- 真实硬件/GPU/NAS 验收只作为 self-hosted runner 的 opt-in 扩展，不阻塞普通 PR。

## 2. 测试层级

| 层级 | 运行位置 | 目的 | 是否阻塞 Phase 9 |
|---|---|---|---|
| L0 Static | GitHub-hosted Ubuntu runner | lint、format、schema、migration 静态检查 | 是 |
| L1 Contract E2E | GitHub-hosted Ubuntu runner | 使用 fake executor 跑完整 API/worker 闭环 | 是 |
| L2 Ubuntu Target E2E | GitHub-hosted Ubuntu runner + Docker target container | 通过真实 SSH 初始化一台 Ubuntu 容器目标机 | 是 |
| L3 Service Integration | GitHub service containers + Docker dependency container | PostgreSQL、Redis、MinIO 依赖集成 | 是 |
| L4 Hardware Smoke | self-hosted runner | 真实 GPU、Docker runtime、NAS、模型缓存验证 | 否，手动/夜间 |

## 3. L1: Fake Executor E2E

Fake executor 用于验证控制面和业务流程，不触碰真实机器。

必须覆盖：

1. 创建机器。
2. 创建 SSH 凭据，验证 API 返回脱敏。
3. 执行机器探测，生成机器画像和机型指纹。
4. 执行 Full Bootstrap Profile，B1-B7 均产生结构化 step result。
5. 注册 mock 模型和 mock framework。
6. 创建 benchmark job。
7. 创建 experiment，并至少产生 2 个 trial。
8. 生成报告 Markdown，并归档 artifact metadata。
9. 验证实验可复现字段完整：machine profile、model hash、runtime mode、framework version、framework params、prompt dataset、launch command。

通过标准：

- 所有 API 返回符合 OpenAPI schema。
- 所有 job 状态最终为 `succeeded` 或预期的 typed failure。
- 数据库中存在完整 experiment/trial/metrics/artifact 记录。
- 不产生明文 password、private key、token。

## 4. L2: Ubuntu Target Container E2E

用 Docker 构造一台“被纳管目标机”：

```text
GitHub-hosted runner
  ├── backend test process
  ├── PostgreSQL service container
  ├── Redis service container
  ├── MinIO dependency container
  └── ubuntu-target Docker container
        ├── openssh-server
        ├── sudo
        ├── test bootstrap user
        └── mutable /etc and /data
```

建议镜像路径：

```text
tests/e2e/images/ubuntu-target/Dockerfile
```

目标镜像要求：

- 基于 `ubuntu:22.04` 和 `ubuntu:24.04` 做 matrix。
- 安装 `openssh-server`、`sudo`、`rsync`、`curl`、`jq`、`python3`。
- 创建初始用户，例如 `seed`，用于模拟首次 SSH 接入。
- 暴露 22 端口，由 workflow 映射到本地随机端口。
- 不内置平台公钥；平台必须在测试中注入。

必须验证的 bootstrap 子集：

| 模块 | CI 验收动作 |
|---|---|
| B1 Access | 注入平台公钥、创建 `inflab` 用户、写 sudoers、二次 SSH 使用平台账号成功 |
| B2 Source | 写入测试镜像源配置；不要求真实 apt upgrade |
| B3 Package | 安装或确认最小工具，如 `jq`、`rsync`；网络失败要给 typed failure |
| B4 Storage | 创建 `/data/models`、`/data/images`、`/data/workspace`、`/data/logs`；LVM/NAS 只做 dry-run |
| B5 Container | Docker 安装和 runtime 配置在 GitHub-hosted runner 中做 dry-run，不在目标容器内装 Docker |
| B6 Tuning | 只记录 baseline，不修改 kernel tuning |
| B7 Bare-Metal | 创建 Python venv，记录 Python/pip freeze；不安装重型推理框架 |

通过标准：

- step runner 使用真实 AsyncSSH 连接 target container。
- 每个 step 都执行 `detect` / `apply` / `verify`。
- 每个 step result 都包含 command、exit code、stdout/stderr artifact URI 或 inline summary、changed files、snapshot、failure hint。
- 重复执行同一个 bootstrap profile，第二次应大部分为 `skipped` 或 `unchanged`，证明幂等。
- 目标容器销毁后不依赖任何持久状态。

## 5. GitHub Actions Workflow

Workflow 文件：

```text
.github/workflows/backend-e2e.yml
```

触发方式：

- `pull_request`：后端、测试、部署、workflow 变更时触发。
- `push` 到 `main`：同上。
- `workflow_dispatch`：手动触发。

当前仓库还没有后端实现，所以 workflow 先保持 preflight 模式。真正启用条件：

```text
backend/pyproject.toml
tests/e2e/backend_e2e_enabled
```

Phase 9 前必须提交 `tests/e2e/backend_e2e_enabled`，让 workflow 从 preflight 升级为强制 E2E。

启用前还必须把 workflow 中的依赖镜像 tag 固定到当时验证过的版本，尤其是 MinIO，避免 `latest` 变化影响验收稳定性。

## 6. Workflow 执行步骤

启用后，`Backend E2E` workflow 应执行：

1. Checkout repository。
2. Install uv and Python。
3. `uv sync --locked --all-extras --dev`。
4. 启动依赖容器：PostgreSQL、Redis 通过 GitHub service containers，MinIO 通过 `docker run`。
5. 执行 Alembic migration。
6. 运行 L0：`uv run ruff check .`、`uv run ruff format --check .`。
7. 运行 L1：`uv run pytest tests/e2e/test_control_plane_fake_executor.py -m e2e`。
8. 构建 Ubuntu target image。
9. 启动 Ubuntu target container，并等待 SSH ready。
10. 运行 L2：`uv run pytest tests/e2e/test_bootstrap_ubuntu_target.py -m e2e_ssh`。
11. 上传失败时的 logs、step artifacts、container inspect、数据库 dump。

## 7. GitHub-hosted Runner 边界

GitHub-hosted runner 可以验证“控制面 + Ubuntu 容器目标机 + 真实 SSH + service containers”，但不能完整代表真实交付环境。

不在 GitHub-hosted runner 中强测：

- GPU 驱动安装。
- NVIDIA Container Toolkit。
- 国产 GPU SDK。
- LVM 真实扩容。
- NAS mount。
- Kernel tuning。
- 大模型下载。
- vLLM/SGLang 重型安装和真实推理。

这些放到 L4 self-hosted runner：

- 标签建议：`self-hosted`, `linux`, `gpu`, `inference-lab`.
- 触发方式：`workflow_dispatch` 或 nightly schedule。
- 目标：一台可重装/可污染的内部测试机。

## 8. 推荐目录

```text
tests/
  e2e/
    backend_e2e_enabled
    conftest.py
    test_control_plane_fake_executor.py
    test_bootstrap_ubuntu_target.py
    images/
      ubuntu-target/
        Dockerfile
    fixtures/
      machine_profiles/
      benchmark_results/
scripts/
  ci/
    wait-for-ssh.sh
    collect-e2e-artifacts.sh
```

## 9. CI 参考依据

- GitHub Actions workflow 文件必须放在 `.github/workflows`。
- GitHub service containers 会为每个 job 创建新容器并在 job 结束后销毁。
- 对需要自定义启动命令的依赖容器，例如 MinIO，可在 workflow step 中用 `docker run` 显式启动。
- 使用 job containers 或 service containers 时必须使用 Linux runner；GitHub-hosted runner 应使用 Ubuntu runner。
- job 直接跑在 runner 上时，service container 端口需要映射到 localhost。
- self-hosted runner 适合真实硬件、内网服务和自定义环境。

官方参考：

- GitHub Actions workflow syntax: https://docs.github.com/actions/reference/workflows-and-actions/workflow-syntax
- GitHub Actions service containers: https://docs.github.com/actions/using-containerized-services/about-service-containers
- GitHub-hosted runners: https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- Self-hosted runners: https://docs.github.com/en/actions/concepts/runners/self-hosted-runners
- uv in GitHub Actions: https://docs.astral.sh/uv/guides/integration/github/
