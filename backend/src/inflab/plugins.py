"""Plugin protocols and built-in MVP fake plugins."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from inflab.schemas import FrameworkParams, PluginInfo, RunSpec, RuntimeMode


class RuntimePlugin(Protocol):
    name: str
    mode: RuntimeMode

    def prepare(self, spec: RunSpec) -> str: ...

    def run_command(self, command: str) -> str: ...


class FrameworkPlugin(Protocol):
    name: str
    supported_runtime_modes: set[RuntimeMode]

    def build_launch_command(self, spec: RunSpec) -> str: ...

    def parse_logs(self, logs: str) -> list[dict[str, str]]: ...


class DriverPlugin(Protocol):
    name: str

    def detect(self) -> dict[str, str]: ...


class ModelPlugin(Protocol):
    name: str

    def verify(self, path: str, expected_sha256: str) -> bool: ...


@dataclass(slots=True)
class BasicRuntimePlugin:
    name: str
    mode: RuntimeMode

    def prepare(self, spec: RunSpec) -> str:
        if self.mode == RuntimeMode.container:
            return f"docker pull inflab/{spec.framework}:{spec.framework_version}"
        return "python3 -m venv /data/workspace/inflab-runtime"

    def run_command(self, command: str) -> str:
        if self.mode == RuntimeMode.container:
            return f"docker run --rm --gpus all inflab-runtime {command}"
        return f"/data/workspace/inflab-runtime/bin/{command}"


class BaseFrameworkPlugin:
    name = "base"
    supported_runtime_modes = {RuntimeMode.container, RuntimeMode.bare_metal}

    def _base_args(self, params: FrameworkParams) -> list[str]:
        args = [
            f"--tensor-parallel-size {params.tensor_parallel_size}",
            f"--pipeline-parallel-size {params.pipeline_parallel_size}",
            f"--gpu-memory-utilization {params.gpu_memory_utilization}",
            f"--max-model-len {params.max_model_len}",
            f"--max-num-seqs {params.max_num_seqs}",
            f"--max-num-batched-tokens {params.max_num_batched_tokens}",
            f"--dtype {params.dtype}",
        ]
        if params.quantization:
            args.append(f"--quantization {params.quantization}")
        if params.enable_chunked_prefill:
            args.append("--enable-chunked-prefill")
        if params.enable_prefix_caching:
            args.append("--enable-prefix-caching")
        return args

    def parse_logs(self, logs: str) -> list[dict[str, str]]:
        events = []
        for line in logs.splitlines():
            match = re.search(r"(ERROR|WARN|INFO):\s*(.*)", line)
            if match:
                events.append({"level": match.group(1).lower(), "message": match.group(2)})
        return events


class VLLMFrameworkPlugin(BaseFrameworkPlugin):
    name = "vllm"

    def build_launch_command(self, spec: RunSpec) -> str:
        args = " ".join(self._base_args(spec.framework_params))
        return f"vllm serve {spec.model_id} {args}"


class SGLangFrameworkPlugin(BaseFrameworkPlugin):
    name = "sglang"

    def build_launch_command(self, spec: RunSpec) -> str:
        args = " ".join(self._base_args(spec.framework_params))
        return f"python -m sglang.launch_server --model-path {spec.model_id} {args}"


class NvidiaDriverPlugin:
    name = "nvidia"

    def detect(self) -> dict[str, str]:
        return {"driver": "mock-550", "cuda": "mock-12.4", "status": "available"}


class SHA256ModelPlugin:
    name = "sha256"

    def verify(self, path: str, expected_sha256: str) -> bool:
        return bool(path and expected_sha256)


class PluginRegistry:
    def __init__(self) -> None:
        self.runtimes: dict[RuntimeMode, RuntimePlugin] = {
            RuntimeMode.container: BasicRuntimePlugin("container", RuntimeMode.container),
            RuntimeMode.bare_metal: BasicRuntimePlugin("bare_metal", RuntimeMode.bare_metal),
        }
        self.frameworks: dict[str, FrameworkPlugin] = {
            "vllm": VLLMFrameworkPlugin(),
            "sglang": SGLangFrameworkPlugin(),
        }
        self.drivers: dict[str, DriverPlugin] = {"nvidia": NvidiaDriverPlugin()}
        self.models: dict[str, ModelPlugin] = {"sha256": SHA256ModelPlugin()}

    def framework(self, name: str) -> FrameworkPlugin:
        return self.frameworks[name]

    def runtime(self, mode: RuntimeMode) -> RuntimePlugin:
        if mode == RuntimeMode.both:
            raise ValueError("runtime plugin requires a single runtime mode")
        return self.runtimes[mode]

    def list_plugins(self) -> list[PluginInfo]:
        plugins = [
            PluginInfo(
                kind="runtime",
                name=plugin.name,
                supported_runtime_modes=[plugin.mode],
                capabilities=["prepare", "run_command"],
            )
            for plugin in self.runtimes.values()
        ]
        plugins.extend(
            PluginInfo(
                kind="framework",
                name=plugin.name,
                supported_runtime_modes=sorted(plugin.supported_runtime_modes),
                capabilities=["build_launch_command", "parse_logs"],
            )
            for plugin in self.frameworks.values()
        )
        plugins.append(
            PluginInfo(
                kind="driver",
                name="nvidia",
                supported_runtime_modes=[RuntimeMode.container, RuntimeMode.bare_metal],
                capabilities=["detect"],
            )
        )
        return plugins


registry = PluginRegistry()
