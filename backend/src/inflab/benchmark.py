"""Benchmark runner models, normalization, and fairness validation."""

from __future__ import annotations

from inflab.plugins import registry
from inflab.schemas import BenchmarkResult, RunSpec


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
