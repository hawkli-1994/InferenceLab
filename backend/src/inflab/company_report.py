"""Company-format benchmark report table generation."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Any

from inflab.db.models import Experiment, ExperimentTrial, Machine, MetricsSummary, ModelRecord

COMPANY_REPORT_COLUMNS = [
    "测试时间",
    "机型",
    "GPU",
    "模型",
    "精度",
    "物理卡数",
    "逻辑卡数",
    "模式",
    "请求并发数",
    "输入",
    "输出",
    "总输入",
    "总输出",
    "请求吞吐",
    "输出吞吐",
    "总吞吐",
    "首Token延时(ms)",
    "每Token延时(ms)",
    "总耗时(s)",
    "平均每用户输出吞吐",
    "备注",
]


def _round(value: float | int | None, digits: int = 2) -> float:
    if value is None:
        return 0.0
    return round(float(value), digits)


def _metric_value(metric: MetricsSummary, key: str, fallback: float = 0.0) -> float:
    raw = metric.metrics.get(key)
    if isinstance(raw, int | float):
        return float(raw)
    attr = getattr(metric, key, None)
    if isinstance(attr, int | float):
        return float(attr)
    return fallback


def _int_value(value: Any, fallback: int = 1) -> int:
    if isinstance(value, int | float):
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    return fallback


def _nested(value: dict[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _machine_type(machine: Machine) -> str:
    profile = machine.machine_profile or {}
    return str(
        profile.get("machine_type")
        or _nested(profile, "system", "product_name")
        or _nested(profile, "system", "model")
        or machine.name
    )


def _gpu_rows(machine: Machine) -> list[dict[str, Any]]:
    rows = _nested(machine.machine_profile or {}, "hardware", "gpu")
    return rows if isinstance(rows, list) else []


def _gpu_name(machine: Machine) -> str:
    names = []
    for row in _gpu_rows(machine):
        if not isinstance(row, dict):
            continue
        name = row.get("model") or row.get("name") or row.get("vendor")
        if name:
            names.append(str(name))
    return ", ".join(dict.fromkeys(names)) or "unknown"


def _physical_gpu_count(machine: Machine, params: dict[str, Any]) -> int:
    total = 0
    for row in _gpu_rows(machine):
        if not isinstance(row, dict):
            continue
        count = row.get("count", 1)
        total += int(count) if isinstance(count, int | float) else 1
    if total > 0:
        return total
    return _int_value(params.get("tensor_parallel_size"), 1)


def _trial_params(experiment: Experiment, trial: ExperimentTrial | None) -> dict[str, Any]:
    if trial and trial.params:
        return trial.params
    return experiment.framework_params or {}


def _benchmark_result(trial: ExperimentTrial | None) -> dict[str, Any]:
    if not trial or not isinstance(trial.result, dict):
        return {}
    result = trial.result.get("benchmark_result")
    return result if isinstance(result, dict) else {}


def _test_time(experiment: Experiment, trial: ExperimentTrial | None) -> str:
    stamp: datetime = trial.created_at if trial else experiment.updated_at
    return stamp.isoformat()


def build_company_report_rows(
    *,
    experiment: Experiment,
    machine: Machine,
    model: ModelRecord,
    metrics: list[MetricsSummary],
    trials_by_id: dict[str, ExperimentTrial],
) -> list[dict[str, str | int | float]]:
    rows: list[dict[str, str | int | float]] = []
    for metric in metrics:
        trial = trials_by_id.get(metric.trial_id or "")
        params = _trial_params(experiment, trial)
        benchmark = _benchmark_result(trial)
        request_count = _int_value(
            metric.metrics.get("request_count") or benchmark.get("request_count"),
            0,
        )
        success_count = _int_value(
            metric.metrics.get("success_count") or benchmark.get("success_count"),
            request_count,
        )
        input_tokens = _int_value(metric.metrics.get("input_tokens"), 1024)
        output_tokens = _int_value(metric.metrics.get("output_tokens"), 256)
        total_input = _int_value(
            metric.metrics.get("total_input_tokens"),
            input_tokens * request_count,
        )
        total_output = _int_value(
            metric.metrics.get("total_output_tokens"),
            output_tokens * success_count,
        )
        output_throughput = _metric_value(metric, "tokens_per_second")
        request_throughput = _metric_value(metric, "requests_per_second")
        total_duration_s = _round(
            metric.metrics.get("total_duration_s")
            if isinstance(metric.metrics.get("total_duration_s"), int | float)
            else total_output / output_throughput
            if output_throughput > 0
            else 0
        )
        total_throughput = _round(
            metric.metrics.get("total_token_throughput")
            if isinstance(metric.metrics.get("total_token_throughput"), int | float)
            else (total_input + total_output) / total_duration_s
            if total_duration_s > 0
            else output_throughput
        )
        logical_cards = _int_value(params.get("tensor_parallel_size"), 1) * _int_value(
            params.get("pipeline_parallel_size"), 1
        )
        request_concurrency = _int_value(
            metric.metrics.get("request_concurrency") or params.get("max_num_seqs") or request_count
        )
        precision = str(params.get("quantization") or params.get("dtype") or "unknown")
        notes = [
            f"trial {trial.trial_index}" if trial else "summary",
            str(experiment.reproducibility.get("mode", "standard")),
            experiment.framework,
        ]
        failure_rate = _metric_value(metric, "failure_rate")
        if failure_rate > 0:
            notes.append(f"failure_rate={_round(failure_rate * 100)}%")
        rows.append(
            {
                "测试时间": _test_time(experiment, trial),
                "机型": _machine_type(machine),
                "GPU": _gpu_name(machine),
                "模型": model.name,
                "精度": precision,
                "物理卡数": _physical_gpu_count(machine, params),
                "逻辑卡数": logical_cards,
                "模式": experiment.runtime_mode,
                "请求并发数": request_concurrency,
                "输入": input_tokens,
                "输出": output_tokens,
                "总输入": total_input,
                "总输出": total_output,
                "请求吞吐": _round(request_throughput),
                "输出吞吐": _round(output_throughput),
                "总吞吐": total_throughput,
                "首Token延时(ms)": _round(_metric_value(metric, "ttft_p50_ms")),
                "每Token延时(ms)": _round(_metric_value(metric, "tpot_p50_ms")),
                "总耗时(s)": total_duration_s,
                "平均每用户输出吞吐": _round(output_throughput / max(request_concurrency, 1)),
                "备注": "; ".join(notes),
            }
        )
    return rows


def render_company_report_csv(rows: list[dict[str, str | int | float]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=COMPANY_REPORT_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in COMPANY_REPORT_COLUMNS})
    return "\ufeff" + output.getvalue()
