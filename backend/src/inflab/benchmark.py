"""Benchmark runner models, normalization, and fairness validation."""

from __future__ import annotations

import json
import re
import shlex
from typing import Any

from inflab.executor import RemoteExecutor
from inflab.plugins import registry
from inflab.schemas import (
    BenchmarkCommandPlan,
    BenchmarkKind,
    BenchmarkPlanCreate,
    BenchmarkResult,
    CommandRecord,
    RunSpec,
)


def build_launch_command(spec: RunSpec) -> str:
    framework = registry.framework(spec.framework)
    runtime = registry.runtime(spec.runtime_mode)
    return runtime.run_command(framework.build_launch_command(spec))


def fake_benchmark_result(spec: RunSpec) -> BenchmarkResult:
    tp = spec.framework_params.tensor_parallel_size
    memory_factor = spec.framework_params.gpu_memory_utilization
    throughput = round(4200 * tp * memory_factor, 2)
    return BenchmarkResult(
        request_count=128,
        success_count=128,
        failure_count=0,
        latency_ms={"p50": 780.0, "p90": 1180.0, "p99": 1480.0},
        ttft_ms={"p50": 110.0, "p90": 180.0, "p99": 260.0},
        tpot_ms={"p50": 18.0, "p90": 24.0, "p99": 32.0},
        throughput={"tokens_per_sec": throughput, "requests_per_sec": round(throughput / 120, 2)},
        gpu={"memory_peak_mb": int(64000 * memory_factor), "utilization_avg": 0.88},
        power={"avg_watt": 2150, "peak_watt": 2380},
        failures=[],
    )


def build_benchmark_command_plan(
    payload: BenchmarkPlanCreate,
    *,
    model_path: str,
) -> BenchmarkCommandPlan:
    result_path = f"{payload.result_dir.rstrip('/')}/{payload.result_filename}"
    serve_command = build_launch_command(payload.run_spec)
    quoted_model = shlex.quote(model_path)
    if payload.run_spec.framework == "sglang":
        bench_command = (
            "python -m sglang.bench_serving --backend sglang "
            f"--model {quoted_model} --host {shlex.quote(payload.host)} --port {payload.port} "
            f"--dataset-name {shlex.quote(payload.dataset_name)} "
            f"--random-input-len {payload.input_len} --random-output-len {payload.output_len} "
            f"--num-prompts {payload.num_prompts} --request-rate {payload.request_rate or 'inf'} "
            f"| tee {shlex.quote(result_path)}"
        )
        return BenchmarkCommandPlan(
            framework="sglang",
            kind=BenchmarkKind.serve,
            serve_command=serve_command,
            bench_command=bench_command,
            result_path=result_path,
            parser="parse_sglang_bench_output",
            notes=[
                "command plan only unless used by the remote benchmark runner",
                "requires sglang installed on the target runtime",
            ],
        )
    if payload.run_spec.framework != "vllm":
        raise ValueError("real benchmark command planning is currently implemented for vllm/sglang")
    common = [
        "vllm",
        "bench",
        payload.kind.value,
        "--model",
        quoted_model,
        "--dataset-name",
        shlex.quote(payload.dataset_name),
        "--num-prompts",
        str(payload.num_prompts),
    ]
    notes = [
        "command plan only; API does not execute real inference by default",
        "requires vLLM installed with bench extras on the target runtime",
    ]

    if payload.kind == BenchmarkKind.serve:
        command_parts = [
            *common,
            "--backend",
            "vllm",
            "--host",
            shlex.quote(payload.host),
            "--port",
            str(payload.port),
            "--random-input-len",
            str(payload.input_len),
            "--random-output-len",
            str(payload.output_len),
            "--save-result",
            "--result-dir",
            shlex.quote(payload.result_dir),
            "--result-filename",
            shlex.quote(payload.result_filename),
        ]
        if payload.request_rate is not None:
            command_parts.extend(["--request-rate", str(payload.request_rate)])
    else:
        command_parts = [
            *common,
            "--input-len",
            str(payload.input_len),
            "--output-len",
            str(payload.output_len),
            "--output-json",
            shlex.quote(result_path),
        ]

    return BenchmarkCommandPlan(
        framework="vllm",
        kind=payload.kind,
        serve_command=serve_command if payload.kind == BenchmarkKind.serve else None,
        bench_command=" ".join(command_parts),
        result_path=result_path,
        parser="parse_vllm_bench_output",
        notes=notes,
    )


def parse_vllm_bench_output(raw: str) -> dict[str, Any]:
    """Parse vLLM bench JSON files or text logs into normalized raw facts."""

    text = raw.strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    facts: dict[str, Any] = {}
    patterns = {
        "request_throughput": r"Request throughput.*?:\s*([0-9.]+)",
        "output_throughput": r"Output token throughput.*?:\s*([0-9.]+)",
        "total_token_throughput": r"Total token throughput.*?:\s*([0-9.]+)",
        "mean_ttft_ms": r"Mean TTFT.*?:\s*([0-9.]+)",
        "median_ttft_ms": r"Median TTFT.*?:\s*([0-9.]+)",
        "p99_ttft_ms": r"P99 TTFT.*?:\s*([0-9.]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, raw, re.IGNORECASE)
        if match:
            facts[key] = float(match.group(1))
    return facts


def parse_sglang_bench_output(raw: str) -> dict[str, Any]:
    facts = parse_vllm_bench_output(raw)
    if facts:
        return facts
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        return {}
    return {}


async def run_remote_benchmark(
    executor: RemoteExecutor,
    plan: BenchmarkCommandPlan,
    *,
    timeout_seconds: int = 3600,
) -> dict[str, Any]:
    logs: list[str] = []
    setup = await executor.run(
        CommandRecord(command=f"mkdir -p {shlex.quote(plan.result_path.rsplit('/', 1)[0])}"),
        timeout_seconds=60,
    )
    if setup.exit_code != 0:
        return {
            "status": "failed",
            "logs": logs,
            "error": setup.stderr,
            "result_path": plan.result_path,
        }

    server_pid: str | None = None
    if plan.serve_command:
        server_log = f"{plan.result_path}.server.log"
        start = await executor.run(
            CommandRecord(
                command=(
                    f"nohup {plan.serve_command} > {shlex.quote(server_log)} 2>&1 "
                    "< /dev/null & echo $!"
                )
            ),
            timeout_seconds=60,
        )
        if start.exit_code != 0:
            return {
                "status": "failed",
                "logs": logs,
                "error": start.stderr,
                "result_path": plan.result_path,
            }
        server_pid = start.stdout.strip().splitlines()[-1] if start.stdout.strip() else None
        await executor.run(CommandRecord(command="sleep 10"), timeout_seconds=20)

    try:
        result = await executor.stream(
            CommandRecord(command=plan.bench_command),
            on_line=logs.append,
            timeout_seconds=timeout_seconds,
        )
    finally:
        if server_pid:
            await executor.run(CommandRecord(command=f"kill {shlex.quote(server_pid)} || true"))

    raw_result = await executor.run(
        CommandRecord(command=f"cat {shlex.quote(plan.result_path)} || true")
    )
    parser = parse_sglang_bench_output if plan.framework == "sglang" else parse_vllm_bench_output
    parsed = parser(raw_result.stdout or "\n".join(logs))
    return {
        "status": "succeeded" if result.exit_code == 0 else "failed",
        "exit_code": result.exit_code,
        "logs": logs,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "result_path": plan.result_path,
        "raw_result": raw_result.stdout,
        "parsed": parsed,
    }


def normalize_metrics(result: BenchmarkResult) -> dict[str, float]:
    return {
        "ttft_p50_ms": result.ttft_ms["p50"],
        "tpot_p50_ms": result.tpot_ms["p50"],
        "latency_p99_ms": result.latency_ms["p99"],
        "tokens_per_second": result.throughput["tokens_per_sec"],
        "requests_per_second": result.throughput["requests_per_sec"],
        "failure_rate": result.failure_count / max(result.request_count, 1),
    }


def validate_fair_comparison(left: RunSpec, right: RunSpec) -> None:
    if left.machine_id != right.machine_id:
        raise ValueError("fair comparison requires the same machine")
    if left.model_id != right.model_id:
        raise ValueError("fair comparison requires the same model hash")
    if left.prompt_dataset != right.prompt_dataset:
        raise ValueError("fair comparison requires the same prompt dataset")
    if left.benchmark_version != right.benchmark_version:
        raise ValueError("fair comparison requires the same benchmark version")
    if left.framework_params != right.framework_params:
        raise ValueError("fair comparison requires the same framework params")
    modes = {left.runtime_mode, right.runtime_mode}
    if {mode.value for mode in modes} != {"container", "bare_metal"}:
        raise ValueError("fair comparison must compare container and bare_metal")
