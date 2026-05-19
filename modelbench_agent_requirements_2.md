# ModelBench Agent / 推理实验室 平台需求设计文档

> 内部代号建议：**Inference Lab** / 对外品牌：**ModelBench Agent**
> 文档版本：**v0.4** (Kickoff Draft)
> v0.4 变更：新增 §0 设计哲学，作为所有需求评审的最高准绳
> v0.3 变更：砍掉企业级反射性需求（RBAC/审计/中断恢复/热加载/隔离），明确"内部 R&D 工具"定位
> v0.2 变更：新增 §4.2 环境接管、§4.3 环境编排（重命名+瘦身）、双运行时（容器 + 裸机）、MVP 延长至 10 周、源神关系反转

---

## 0. 设计哲学（最高准绳）

> **我们做的不是企业级花瓶，而是作坊级的真正好用的工具。**

所有需求、所有功能、所有抽象都先过这条线。冲突时这一节赢。

### 作坊级 ≠ 简陋，而是：

- **每一行代码、每个字段、每个 UI 元素都有人真的会用**。三个工程师 + 几个售前 + 几个研发，没人需要看"系统健康度仪表盘"
- **能用脚本写完的不做平台**。5 行 bash 能跑完的事，不建微服务
- **重做的成本 < 防御性设计的成本**。机器搞坏重装 30 分钟，写回滚机制要 3 天 + 永远在维护——账要这么算
- **数据真实可信 > 系统多稳健**。客户问"数据真测出来的吗"，没人问"你们 SLA 几个 9"
- **能不抽象就别抽象**。`FrameworkPlugin` 要做（真有多个框架）；"插件热加载"不做（生产时不会有人换插件）

### 真正好用 ≠ 功能多，而是：

- **跑通一次完整流程的时长** 是首要指标。从 SSH 输入到 PDF 报告，能压多短压多短
- **失败时的错误信息要让人立刻知道下一步**。不是 "Internal Server Error"，而是 "vLLM OOM，建议把 max-num-seqs 从 256 降到 128"
- **常见操作 3 次点击内完成**。加机器 → 选模型 → 跑测试，一气呵成
- **每个测试都能一键复现**。报告里的启动命令直接复制就能跑
- **工程师自己天天用它**。检验"好用"的唯一标准——如果你们三个自己都嫌弃用平台不如直接 SSH 手敲，就是没做好

### 花瓶检测器

每个新需求过一遍：
> **删掉它，团队或客户在 3 个月内会有人抱怨吗？**
> 不会 → 删。

---

---

## 1. 产品定位

**一句话定位**：面向 AI 整机厂商的自动化模型推理测试、调优与报告平台。

**解决的核心问题**：把"机器交付前的推理验证"从人工试错（驱动装一遍、模型传一遍、参数调一遍、报告写一遍）转化为**可复用、可量化、可沉淀**的工程能力。

**与公司战略的耦合点**：

- 直接服务 Agent 一体机的"机型 × 模型 × 框架"全矩阵覆盖
- 是国产 GPU（瀚博、昇腾、海光、沐曦、寒武纪等）适配工作的标准化抓手
- 沉淀一份长期可复用的性能数据资产
- 可作为开源旗舰项目对外形成行业影响力

**与 GPUStack 等部署平台的差异化**：本平台是**整机厂的"性能验证 + 售前售后工具"**，交付物是性能报告与最佳启动参数，生命周期是一次性测试任务；GPUStack 是部署侧 MaaS 平台，交付物是长期运行的推理服务。两者面向产业链不同环节，不冲突。

---

## 2. 业务场景

| 场景 | 触发方 | 价值 |
|---|---|---|
| 整机交付前性能验证 | 生产 / QA | 防止现场返工 |
| 国产 GPU 适配验证 | 研发 | 标准化适配流程 |
| 新模型上架评估 | 模型团队 | 快速回答"这卡能不能跑 X 模型" |
| 售前 POC | 售前 / 客户成功 | 客户现场快速演示最佳配置 |
| 售后参数调优 | 交付工程 | 现场重新跑一遍找最优 |
| 性能白皮书 / 客户报告 | 市场 / 售前 | 自动产出，免去手写 |
| 推理框架版本回归 | 研发 | vLLM/SGLang 升级时回归测试 |
| 容器 vs 裸机性能对比 | 研发 / 售前 | 回答"裸装和容器方案差多少" |

---

## 3. 目标用户

- **售前工程师**：用平台跑客户场景，导出报告
- **研发工程师**：调试新框架、新驱动、新模型
- **测试工程师**：建立性能基线，做回归测试
- **产品经理**：看跨机型对比，做选型决策
- **客户工程师**：到客户现场用平台调优

---

## 4. 核心功能需求

### 4.1 机器纳管（Machine Onboarding）

**输入**：

- SSH 连接信息：host / port / user / private key 或 password
- 初始 sudo 凭据（可选）
- 集群模式：单机 / 多机 / 异构集群

**自动探测项**：

- **硬件**：主板型号、BIOS 版本、BMC/IPMI、CPU 型号/核数/频率、内存容量/通道/频率、GPU 型号/数量/显存/PCIe Gen、磁盘类型/容量/IOPS 基线、网卡（含 RDMA/IB/RoCE 能力）
- **拓扑**：PCIe Switch 拓扑、NUMA 节点、NVLink/NVSwitch、国产卡片间互联
- **系统**：OS 发行版与内核、GLIBC、Python、CUDA/ROCm/CANN/Vastai SDK 版本
- **容器**：Docker、NVIDIA Container Toolkit、国产 GPU 容器运行时

**输出**：

- 机器画像 JSON（结构化、可入库）
- **机型指纹**（哈希），用于和历史测试数据匹配
- 进入 Onboarding Pool，等待执行 §4.2 环境接管

---

### 4.2 环境接管（Environment Bootstrap）★ v0.2 新增

**目标**：把裸机/原生 Ubuntu **一次性**拉到"可测试基线"状态，机器入册时执行一次，之后只在显式重做时重跑。

**与 §4.3 环境编排的边界**：

- **§4.2 接管**：一次性动作，从裸机拉到 Ready Pool，**不绑死任何具体测试版本**
- **§4.3 编排**：每次测试任务时，按需切换驱动/框架/镜像/模型版本

**设计原则**：子模块可独立执行。这是**内部测试机**，搞坏了重装即可，不为"原子事务/自动回滚/中断恢复"过度设计。

**Bootstrap Profile**（onboarding 时由用户选择）：

| Profile | 包含模块 | 适用场景 |
|---|---|---|
| Minimal | B1+B2 | 机器已基本就绪，只补镜像源 |
| Standard Container | B1-B6（不含 B7） | 只走容器路径的测试 |
| Standard Bare-Metal | B1-B4 + B6 + B7 | 只走裸机路径的测试 |
| **Full**（默认推荐） | 全部 | 同时具备容器和裸机两种测试能力 |
| Custom | 自由勾选 | — |

#### B1. 访问接管（Access Bootstrap）

- 注入平台公钥到 root 和测试账号
- 创建/校准统一测试账号（如 `inflab`），统一密码（从平台密钥库拉取）
- 配置 `sudo NOPASSWD`（仅测试账号）
- sshd 放开 root 直连与密码认证（**内网测试环境默认行为**）
- 重启 sshd 前预留备份连接，避免锁死

**说明**：平台只服务公司内网测试环境，权限放开就是默认行为。机器画像里加个 `access_mode = permissive` 标签即可，不做自动收回、不做公网 IP 检测——这是网络层的事，平台层不掺和。

#### B2. 源接管（Source Bootstrap）

平台**自建轻量 mirror 配置模块**，覆盖：

- APT sources.list（含 security/updates）
- pip / Poetry / uv 镜像
- npm / yarn / pnpm
- Docker registry mirror（写入 daemon.json）
- HuggingFace endpoint
- ModelScope / Conda / cargo / go proxy

**与源神（Yuanshen）项目的关系——关系反转**：

源神当前尚不成熟，本平台**不强制集成源神**。**反向路径**：平台先把 B2 做出来跑稳，沉淀真实生产需求和踩坑数据；待平台稳定后，再把这块抽离出来反哺源神，让源神演进为平台的外部依赖。这样源神的设计被真实生产需求驱动，而非反过来。

#### B3. 包接管（Package Bootstrap）

- 基础工具：vim、tmux、htop、nvtop、jq、curl、wget、git、rsync、iperf3、stress-ng、numactl 等
- 编译工具链：build-essential、cmake、ninja
- Python 多版本：pyenv 或 conda/mamba（**裸机推理路径 B7 的前置依赖**）
- 监控代理:node_exporter、可选 nvidia-dcgm-exporter

#### B4. 存储接管（Storage Bootstrap）

**第一版只支持单一公司 NAS**，多 NAS 源后续扩展。

**探测**：

- 当前分区表、文件系统、剩余空间
- LVM 卷组与未分配空间
- NVMe / SSD / HDD 分类
- IOPS 基线（fio 短跑）

**接管动作**：

- LVM 自动扩容（未分配空间合并到 `/` 或专用卷）
- 创建标准目录结构：`/data/models`、`/data/images`、`/data/workspace`、`/data/logs`
- 挂载公司 NAS（NFS/CIFS），写入 `/etc/fstab` 持久化
- **缓存策略**：
  - 冷数据：NAS 直连读取
  - 热数据：rsync 到本地 NVMe，软链或 bind mount 暴露给推理框架
  - 缓存淘汰：LRU + 容量水位线（本地 80% 触发清理）

**记录**：分区/挂载操作前把当前 `lsblk` 输出写入实验日志，万一搞错了能查到改过什么。不做"强制二次确认"——内部测试机搞坏了重装即可。

#### B5. 容器接管（Container Bootstrap）

- Docker CE 安装 + 配置（daemon.json：registry mirror、storage driver、log rotation、default-runtime）
- NVIDIA Container Toolkit（或对应国产 GPU 的容器运行时）
- **平台内置镜像分发**：
  - 平台维护内置镜像仓库（rsync 友好的目录结构 + manifest）
  - 离线场景：`docker save | rsync | docker load`
  - 在线场景：私有 registry pull
  - 镜像清单和 SHA256 入库，避免重复传输

#### B6. 系统调优（Kernel & System Tuning）

可选 profile：

| Profile | 适用场景 |
|---|---|
| `inference-throughput` | CPU governor=performance、关闭 THP、HugePages 预留、NUMA balancing off、TCP 大缓冲、关闭 swap |
| `inference-latency` | throughput 基础上禁用 C-states、IRQ affinity 绑定、关闭 turbo 波动 |
| `baseline` | 完全不动系统，作为"未调优 vs 调优"对比基准 |
| `power-test` | 保留默认调度，用于功耗对比 |

**GPU 相关**：persistence mode、power limit、MIG 配置（如适用）、ECC on/off。

#### B7. 裸机运行时（Bare-Metal Runtime）

平台**双运行时之一**，与 B5 容器路径并行。

- conda/mamba 或 venv 创建隔离环境
- 直接 pip 安装 vLLM / SGLang（不走容器）
- 驱动直接装在 host（不走 Container Toolkit）
- 模型/权重直接读本地路径

**产品价值**：客户经常问"我直接装 vLLM 和你给的容器方案差多少？"——双运行时性能对比本身就是高价值报告内容，也更接近某些客户的裸机交付场景。

机器画像中记录 `runtime_mode = container | bare_metal | both`，§4.3 编排和 §4.7 调参按对应路径走。

---

### 4.3 环境编排（Per-Test Provisioning）★ v0.2 重命名 + 瘦身

每次测试任务前的按需切换。前提：机器已完成 §4.2 接管。

**第一版支持**：

- Ubuntu 22.04 / 24.04
- NVIDIA 主流驱动（535 / 550 / 570 / 595），支持同机器多驱动版本切换
- vLLM、SGLang 多版本（pip 或 docker 镜像维度）

**插件化扩展（后续）**：

- 国产 GPU 驱动：瀚博 Vastai、昇腾 CANN、海光 ROCm、沐曦、寒武纪
- 其他框架：TensorRT-LLM、llama.cpp、Ollama、MindIE
- RDMA 驱动（Mellanox OFED / iWARP）

**关键设计**：所有切换动作幂等可重试，**测试结束后能回到 §4.2 接管完成的 baseline 状态**——这是保证下一个测试任务不被污染的关键。

### 4.4 模型分发

**三种模式**：

1. 内网 **rsync**（首选，对接公司模型仓库；B4 NAS 缓存层在此层之上）
2. **NFS / MinIO** 挂载
3. **HuggingFace / ModelScope** 下载（公网或镜像）

**要求**：

- 权重 SHA256 校验
- 断点续传
- 权重格式转换：FP16 / BF16 / FP8 / INT8 / INT4 / AWQ / GPTQ
- 与公司模型仓库 API 打通（统一身份认证）

### 4.5 推理框架管理

**第一版**：vLLM、SGLang（**容器 + 裸机两种安装方式都要支持**）

**扩展**：TensorRT-LLM、llama.cpp、Ollama、MindIE（昇腾）、Vastai 自研栈

每个框架实现 `FrameworkPlugin` 统一接口（见 §6）。**接口设计必须支持 container/bare_metal 双路径**——这是 v0.2 的关键变化。

### 4.6 Benchmark Runner

**核心性能指标**：

- TTFT（Time To First Token）
- TPOT（Time Per Output Token）
- 端到端延迟 P50 / P90 / P99
- 吞吐：tokens/s、requests/s
- 显存峰值与稳态占用
- GPU / CPU 利用率
- 整机功耗（W）
- 失败率与错误码分布

**测试场景**：

- 单请求基线
- 固定并发压测
- 阶梯并发（ramp-up）
- 长上下文（32K / 128K / 256K）
- 批量 prompt
- 真实任务集：代码生成 / 多轮对话 / RAG / Agent 工具调用
- **容器 vs 裸机对比测试**（同模型、同参数、同硬件，仅 runtime_mode 不同）

### 4.7 Agent 自动调参（平台最大差异化能力）

**调参空间示例（vLLM）**：

`tensor-parallel-size`、`pipeline-parallel-size`、`gpu-memory-utilization`、`max-model-len`、`max-num-seqs`、`max-num-batched-tokens`、`enable-chunked-prefill`、`kv-cache-dtype`、`quantization`、`dtype`、`enable-prefix-caching`、speculative decoding 相关。

**目标函数**（用户在 UI 选择）：

- 最大吞吐
- 最低 P99 延迟
- 最大并发数
- 最大上下文窗口
- 多目标帕累托前沿（吞吐 vs 延迟）
- 最稳配置（失败率最低）

**Agent 决策循环**：

```
  ┌─────────────────────────────────────────┐
  │  Goal: 找出 Qwen3-32B 在 4×A100 最优配置 │
  └─────────────────────────────────────────┘
              │
   ┌──────────▼──────────┐
   │   1. Observe        │ ← 机器画像 + 历史经验库
   └──────────┬──────────┘
   ┌──────────▼──────────┐
   │   2. Plan           │ ← 规则 + LLM 规划 + 启发式剪枝
   └──────────┬──────────┘
   ┌──────────▼──────────┐
   │   3. Act            │ ← 远程启动测试 + 收集指标
   └──────────┬──────────┘
   ┌──────────▼──────────┐
   │   4. Reflect        │ ← 解析结果, 更新经验库
   └──────────┬──────────┘
              │ 未达目标且预算未用完 → 回到 Observe
              │ 达到目标或预算耗尽 → 输出最优 + 报告
```

**第一版策略**：

- Grid + Random Search（保底）
- LLM 规划（用 Claude/Kimi 生成候选参数组合并解释理由）
- 启发式剪枝（避免显存不足、避免明显劣解）
- **预算控制**：用户可设定最大测试轮数、最长总时长、最大功耗预算

**后续演进**：

- 贝叶斯优化（Optuna / Ax）
- 经验迁移：相似机型的历史最优作为先验
- 多目标进化算法（NSGA-II）做帕累托前沿

### 4.8 实验记录与数据资产（长期价值核心）

**所有测试都写入结构化数据库**，字段必须覆盖：

| 类别 | 字段 |
|---|---|
| 机器 | 主板型号、BIOS、BMC、CPU、GPU、内存、磁盘、网卡、PCIe/NUMA 拓扑 |
| **Bootstrap 状态**（v0.2 新增） | profile、应用时间、各子模块状态、快照路径 |
| **Runtime Mode**（v0.2 新增） | container / bare_metal |
| 软件 | OS、内核、驱动版本、容器运行时、Python、框架版本 |
| 模型 | 名称、参数量、量化方式、权重哈希、上下文窗口 |
| 测试参数 | 并发数、输入/输出长度、prompt 集、场景标签 |
| 框架参数 | 完整启动命令（可一键复现） |
| 性能指标 | 上述所有指标 + 时序数据 |
| 日志 | 框架日志、系统日志、dmesg、错误堆栈 |
| 失败分类 | OOM / 驱动错误 / 配置错误 / 性能不达标 / 超时 / 其他 |

**Bootstrap 字段示例**：

```yaml
bootstrap:
  profile: "Full"
  applied_at: 2026-05-20T10:00:00Z
  modules:
    access:     {mode: permissive, root_login: true, applied: true}
    source:     {mirror_set: "company-internal", applied: true}
    package:    {python_versions: ["3.10", "3.11"], applied: true}
    storage:    {nas_mounted: ["//nas/models"], local_cache: "/data", applied: true}
    container:  {docker_version: "27.3", toolkit_version: "1.16", applied: true}
    tuning:     {profile: "inference-throughput", reversible: true, applied: true}
    bare_metal: {python_envs: ["py310-vllm", "py311-sglang"], applied: true}
  snapshots:
    pre_bootstrap: "/var/snapshots/pre_bootstrap_20260520.tar.gz"
    pre_tuning:    "/var/snapshots/pre_tuning_20260520.tar.gz"

experiment:
  runtime_mode: container  # 此次具体测试用的运行时
  # ... 其余字段
```

**数据资产长期价值**：售前快速报价、选型决策、研发优先级判断、行业基准数据。

### 4.9 可视化

- 实时仪表盘（测试运行中的指标流）
- 历史实验对比（多个实验并排）
- 参数空间扫描热力图
- 帕累托前沿图
- 跨机型横向对比矩阵
- 同模型在不同机型上的性能雷达图
- **容器 vs 裸机对比视图**（v0.2 新增）

### 4.10 报告生成

**输出格式**：Markdown → PDF / DOCX

**报告内容**：

- 一页摘要（结论 + 推荐配置）
- 硬件 / 软件 / 模型 / 框架完整信息
- **Bootstrap 配置摘要**（v0.2 新增：哪些 profile 应用了、调优 vs 未调优对比）
- 测试方法学
- 性能曲线（图表）
- **最佳推荐配置 + 完整启动命令**（区分容器和裸机）
- **容器 vs 裸机性能差异分析**（v0.2 新增）
- 失败配置与原因
- 瓶颈分析（GPU / 带宽 / CPU / 内存 / 网络）
- 调优过程时间线
- 部署建议
- 风险与已知坑

**模板**：

- 内部研发报告
- 客户交付报告（支持品牌定制：客户 logo、封面、抬头）
- 性能白皮书（行业发布用）

---

## 5. 系统架构

```
┌────────────────────────────────────────────┐
│   Web UI  (React + ECharts)                │
└────────────────┬───────────────────────────┘
                 │
┌────────────────▼───────────────────────────┐
│   Control Plane API  (FastAPI / Go)        │
└────────────────┬───────────────────────────┘
                 │
   ┌─────────────┼─────────────┐
   │             │             │
┌──▼────┐  ┌─────▼─────┐  ┌────▼──────┐
│ Job   │  │ Experiment│  │  Report   │
│ Sched │  │  Database │  │ Generator │
└──┬────┘  └─────┬─────┘  └───────────┘
   │            │
┌──▼────────────▼────────────────────────┐
│ Remote Executor (SSH + Ansible-like)   │
│  ├── Bootstrap Playbooks (B1-B7)       │← v0.2 新增层
│  └── Provisioning Playbooks            │
└──┬─────────────────────────────────────┘
   │
┌──▼─────────────────────────────────────┐
│ Target Machine                         │
│  ├── DriverPlugin                      │
│  ├── RuntimePlugin (Container/Bare)    │← v0.2 双路径
│  ├── FrameworkPlugin (vLLM/SGLang/...) │
│  └── ModelPlugin                       │
└────────────────────────────────────────┘
```

**技术选型建议**：

- Backend：FastAPI（首选，生态好）或 Go（性能更稳）
- Frontend：React + ECharts / AntV
- Remote Exec：自研轻量 SSH executor，参考 Ansible playbook 模式
- 主库：PostgreSQL（结构化指标）
- 时序：Prometheus 格式（直接复用社区生态）
- 报告：Markdown → Pandoc → PDF/DOCX
- 制品库：MinIO（模型、镜像、报告、bootstrap 快照）

---

## 6. 插件化架构

四类插件，每类一个抽象接口。**v0.2 关键变化：所有运行时相关接口必须区分 container/bare_metal 两种实现**。

### DriverPlugin

```python
class DriverPlugin:
    def detect(self) -> DriverInfo: ...
    def install(self, version: str, mode: RuntimeMode) -> InstallResult: ...
    def uninstall(self) -> None: ...
    def health_check(self) -> HealthStatus: ...
```

### RuntimePlugin（容器/裸机层）

```python
class RuntimePlugin:
    mode: Literal["container", "bare_metal"]
    def prepare(self) -> None: ...
    def pull_image(self, image: str) -> None: ...           # 容器路径
    def setup_venv(self, python_version: str) -> None: ...  # 裸机路径
    def run(self, spec: RunSpec) -> RuntimeHandle: ...
```

### FrameworkPlugin（最核心）

```python
class FrameworkPlugin:
    def install(self, runtime: RuntimePlugin) -> None: ...
    def prepare_model(self, model: ModelSpec) -> None: ...
    def start_server(self, params: FrameworkParams, runtime: RuntimePlugin) -> ServerHandle: ...
    def health_check(self) -> bool: ...
    def collect_metrics(self) -> Metrics: ...
    def stop(self) -> None: ...
    def parse_logs(self, logs: str) -> StructuredEvents: ...
```

### ModelPlugin

```python
class ModelPlugin:
    def download(self, source: ModelSource) -> Path: ...
    def verify(self, path: Path) -> bool: ...
    def convert(self, path: Path, target_format: str) -> Path: ...
```

---

## 7. 非功能需求

刻意保持轻薄——这是**内部 R&D 工具**，不是企业级 SaaS。明确**不在 MVP 范围内**：RBAC、审计日志、断点续测、任务自动重试、插件热加载、测试隔离机制、HA/灾备。这些东西出问题时，重跑/重启/重装就够了。

真正关心的只有两点：

| 维度 | 指标 |
|---|---|
| 并发管理能力 | 单实例能纳管 10+ 目标机器（一机一测，不抢占） |
| 数据保留 | 实验数据至少保留 1 年——**数据本身是核心资产**，丢了才是真的疼 |

其他一切以"够用就行、坏了重做"为原则。

---

## 8. MVP 范围与 **10 周路线**（v0.2 由 8 周延长）

**延长原因**：v0.2 新增 7 个 bootstrap 子模块 + 双运行时（容器 + 裸机）并行，实际工作量较原方案增加约 25%。原 8 周路线硬塞会导致 bootstrap 层做不扎实，反而拖累后续。

| 周次 | 任务 |
|---|---|
| W1-2 | SSH 纳管 + 硬件探测 + **B1 访问接管** + **B2 源接管**（基础版） |
| W3-4 | **B3 包接管** + **B4 存储接管**（含 NAS 挂载 + rsync 缓存） |
| W5 | **B5 容器接管** + 容器路径 vLLM 跑通 |
| W6 | **B7 裸机运行时** + 裸机路径 vLLM 跑通 |
| W7 | 基础 Benchmark + **容器 vs 裸机性能对比** |
| W8 | Agent 调参（规则 + LLM 规划） + 失败记录 |
| W9 | 报告导出（PDF/DOCX） + 多机对比 |
| W10 | Demo 视频 + 内部发布 + 文档 |

**MVP 范围内明确不做**（推迟到 v1.1+）：

- **B6 系统调优 profile**（MVP 用 baseline 即可，调优 profile 的价值在 v1.1 通过"调优 vs 未调优"对比报告体现）
- **国产 GPU 适配**（瀚博 VA16 作为 v1.1 第一个国产 GPU 插件验证）
- **多机分布式推理**（v1.2+）

**3 人分工建议**（v0.2 调整）：

- **你**：架构设计、Bootstrap profile 设计、插件协议（含 container/bare_metal 抽象）、Agent 调优逻辑、报告模板标准
- **工程师 A**：B1-B5 接管模块、远程 SSH 执行框架、Benchmark Runner、指标采集
- **工程师 B**：B7 裸机运行时、Web UI、实验数据库、可视化、报告导出

---

## 9. MVP Demo 场景（用来打动领导）

> 输入一台 4 卡 NVIDIA 服务器的 SSH 信息（**裸机状态**：刚装好的 Ubuntu，无 Docker、无模型、原生镜像源）
> 选择 Bootstrap Profile：**Full**
> 选择模型：Qwen3-32B 或 DeepSeek-R1-Distill-Qwen-32B
> 选择框架：vLLM（**同时跑容器和裸机两种 runtime**）
> 设定目标：在 P99 延迟 < 2s 的约束下追求最高吞吐
> 平台全自动完成：环境接管 → 模型同步 → 双路径测试 → 参数搜索 → 性能测试 → 报告生成
> 最终输出：**容器路径最佳启动命令 + 裸机路径最佳启动命令 + 两者对比 + 完整 PDF 报告**

这个 demo 比 v0.1 版本更震撼，因为它从"裸机一键到性能报告"完整闭环，而且容器 vs 裸机对比是一个非常直观的"销售爆点"。

---

## 10. 风险与挑战

| 风险 | 应对 |
|---|---|
| 国产 GPU 驱动碎片化 | 插件化是关键，每家一个 Plugin 独立维护 |
| 模型权重传输带宽瓶颈 | 内网 rsync 优先，B4 提供 NAS + 本地 NVMe 双层缓存 |
| 长尾故障难复现 | 强制记录 dmesg / syslog / 框架日志，按机器画像归档 |
| Agent 调参成本不可控 | 强制设预算上限（轮数 / 时长 / 功耗），随时可中断 |
| 报告需要客户定制 | 模板引擎 + 品牌占位符 |
| 公司 NAS 带宽 | 多机并发 rsync 可能打爆 NAS，平台层做并发限流 |
| 双运行时维护成本 | 容器和裸机两套适配在插件接口层做强抽象，避免分叉 |

---

## 11. 长期演进方向

- **多机分布式推理测试**：TP + PP + EP 并行的全自动验证
- **推理框架 A/B 对比**：同模型同硬件下 vLLM vs SGLang vs TRT-LLM 自动跑分
- **CI/CD 集成**：新驱动/新框架/新模型发布时自动触发回归
- **经验迁移**：历史最优参数作为新机型搜索的先验，大幅加速调参
- **行业基准**：类似 MLPerf 的整机厂商版基准，对外发布形成话语权
- **开源社区**：作为开源项目运营，吸引外部贡献国产 GPU 插件，形成生态
- **B6 调优 profile 量化研究**：基于平台数据回答"调优带来多少收益"——本身就是有传播价值的内容

---

## 12. 与现有工作的协同

- **瀚博 VA16 评估**：第一个国产 GPU 适配案例，v1.1 直接用平台跑评估，沉淀第一份"国产卡 + 主流框架 + 主流模型"基准数据
- **MiniMax M2.7 / Kimi K2.5 / GLM-5 部署**：作为模型库的初始内容
- **源神（GitHub 镜像配置工具）—— 关系反转 (v0.2)**：源神当前尚不成熟，本平台**不强制集成**。反向路径：平台先把 B2 源接管做出来跑稳，沉淀真实生产需求和踩坑数据；待平台稳定后将这块抽离出来反哺源神，让源神演进为被生产平台依赖的基础库。这条路径让源神的设计被真实需求驱动，而非反过来——对源神的长期价值更高
- **Kata Containers + GPU Passthrough 经验**：未来的 RuntimePlugin 之一，做强隔离测试时可用

---

*文档维护人：Husa | 当前版本：v0.4 | 下一步：v0.5 待 W2 结束后基于实际进展更新*
