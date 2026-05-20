import pytest

from inflab.benchmark import (
    build_benchmark_command_plan,
    fake_benchmark_result,
    normalize_metrics,
    parse_vllm_bench_output,
    validate_fair_comparison,
)
from inflab.executor import ExecutionContext, FakeExecutor
from inflab.plugins import registry
from inflab.reports import render_markdown_report
from inflab.schemas import BenchmarkPlanCreate, FrameworkParams, RunSpec
from inflab.security import decrypt_secret, encrypt_secret
from inflab.steps import resolve_bootstrap_steps, run_steps
from inflab.tuning import heuristic_prune, plan_candidates


def run_spec(runtime_mode: str = "container") -> RunSpec:
    return RunSpec(
        machine_id="machine-1",
        model_id="model-1",
        runtime_mode=runtime_mode,
        framework="vllm",
        framework_params=FrameworkParams(tensor_parallel_size=2),
        prompt_dataset="prompts",
        benchmark_version="bench-v1",
    )


@pytest.mark.asyncio
async def test_step_runner_records_detect_apply_verify() -> None:
    steps = resolve_bootstrap_steps("minimal")
    results = await run_steps(
        steps,
        ExecutionContext(machine_id="machine-1", dry_run=True),
        FakeExecutor(),
    )

    assert [result.id for result in results] == ["B1", "B2"]
    assert all(set(result.phase_results) == {"detect", "apply", "verify"} for result in results)
    assert all(result.stdout_uri for result in results)


def test_plugins_generate_runtime_specific_commands() -> None:
    spec = run_spec("bare_metal")
    command = registry.runtime(spec.runtime_mode).run_command(
        registry.framework("vllm").build_launch_command(spec)
    )

    assert "/data/workspace/inflab-runtime/bin/vllm serve" in command
    assert registry.framework("sglang").parse_logs("INFO: ready") == [
        {"level": "info", "message": "ready"}
    ]


def test_benchmark_normalization_and_fairness() -> None:
    left = run_spec("container")
    right = run_spec("bare_metal")
    result = fake_benchmark_result(left)
    metrics = normalize_metrics(result)

    assert metrics["tokens_per_second"] > 0
    validate_fair_comparison(left, right)

    with pytest.raises(ValueError, match="same prompt dataset"):
        validate_fair_comparison(left, right.model_copy(update={"prompt_dataset": "other"}))


def test_vllm_benchmark_command_plan_and_parser() -> None:
    plan = build_benchmark_command_plan(
        BenchmarkPlanCreate(run_spec=run_spec("container"), kind="serve", num_prompts=8),
        model_path="/data/models/qwen3",
    )

    assert "vllm bench serve" in plan.bench_command
    assert "--save-result" in plan.bench_command
    assert plan.result_path.endswith("vllm-bench-result.json")

    parsed = parse_vllm_bench_output(
        "Request throughput (req/s): 12.5\n"
        "Output token throughput (tok/s): 4096.0\n"
        "P99 TTFT (ms): 230.0\n"
    )
    assert parsed["request_throughput"] == 12.5
    assert parsed["output_throughput"] == 4096.0
    assert parsed["p99_ttft_ms"] == 230.0


def test_tuning_candidates_are_valid_and_pruned() -> None:
    phases, candidates = plan_candidates(gpu_count=4, max_trials=3)

    assert phases[0] == "Observe"
    assert len(candidates) == 3
    assert heuristic_prune([FrameworkParams(max_model_len=1_000_000, max_num_seqs=2)]) == []


def test_report_redaction_and_secret_encryption(settings) -> None:
    encrypted = encrypt_secret("secret-token", settings.secret_key)
    assert encrypted != "secret-token"
    assert decrypt_secret(encrypted, settings.secret_key) == "secret-token"

    report = render_markdown_report(
        name="test",
        runtime_mode="container",
        framework="vllm",
        framework_version="mock",
        prompt_dataset="prompts",
        launch_command="password=secret-token vllm serve",
        reproducibility={},
        metrics={},
    )
    assert "secret-token" not in report
    assert "[REDACTED]" in report
