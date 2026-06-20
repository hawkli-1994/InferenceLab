import pytest

from inflab.agent_executor import intelligent_worker_prompt, pi_agent_executor_plan
from inflab.artifacts import (
    distribute_model,
    model_distribution_command,
    model_verification_command,
)
from inflab.autoresearch_integration import autoresearch_integration_plan
from inflab.benchmark import (
    build_benchmark_command_plan,
    fake_benchmark_result,
    normalize_metrics,
    parse_vllm_bench_output,
    run_remote_benchmark,
    validate_fair_comparison,
)
from inflab.config import AgentExecutorSettings
from inflab.executor import ExecutionContext, FakeExecutor
from inflab.llm_provider import LiteLLMCandidateProvider
from inflab.plugins import registry
from inflab.probe import parse_nvidia_smi_csv
from inflab.reports import export_report, render_markdown_report
from inflab.schemas import BenchmarkPlanCreate, FrameworkParams, RunSpec
from inflab.security import decrypt_secret, encrypt_secret
from inflab.steps import resolve_bootstrap_steps, run_steps
from inflab.tuning import heuristic_prune, plan_candidates, standard_matrix


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


def test_sglang_benchmark_command_plan() -> None:
    spec = run_spec("container").model_copy(update={"framework": "sglang"})
    plan = build_benchmark_command_plan(
        BenchmarkPlanCreate(run_spec=spec, kind="serve", num_prompts=8),
        model_path="/data/models/qwen3",
    )

    assert "python -m sglang.bench_serving" in plan.bench_command
    assert "--backend sglang" in plan.bench_command
    assert plan.serve_command


@pytest.mark.asyncio
async def test_remote_benchmark_runner_streams_and_collects_result() -> None:
    plan = build_benchmark_command_plan(
        BenchmarkPlanCreate(run_spec=run_spec("container"), kind="throughput", num_prompts=8),
        model_path="/data/models/qwen3",
    )
    executor = FakeExecutor()

    result = await run_remote_benchmark(executor, plan)

    assert result["status"] == "succeeded"
    assert any("vllm bench throughput" in command.command for command in executor.commands)


@pytest.mark.asyncio
async def test_model_distribution_builds_real_remote_commands() -> None:
    assert "huggingface-cli download" in model_distribution_command(
        "huggingface", "Qwen/Qwen3", "/data/models/qwen3"
    )
    executor = FakeExecutor()

    result = await distribute_model(
        executor,
        source="rsync",
        cache_path="/cache/qwen",
        target_path="/data/models/qwen",
        expected_sha256="expected",
    )

    assert result["exit_code"] == 0
    assert "rsync" in result["command"]
    assert "sha256 mismatch" in result["verify_command"]
    assert "expected" in result["verify_command"]


def test_model_verification_command_compares_expected_hash() -> None:
    command = model_verification_command("/data/models/qwen", "abc123")

    assert 'test "$actual" = abc123' in command
    assert "sha256sum" in command


def test_probe_parses_nvidia_smi_csv() -> None:
    rows = parse_nvidia_smi_csv("0, NVIDIA A100, 81920, 550.54, 12.4")

    assert rows == [
        {
            "index": 0,
            "vendor": "nvidia",
            "model": "NVIDIA A100",
            "memory_mb": 81920.0,
            "driver_version": "550.54",
            "cuda_version": "12.4",
        }
    ]


def test_tuning_candidates_are_valid_and_pruned() -> None:
    phases, candidates = plan_candidates(gpu_count=4, max_trials=3, mode="intelligent")

    assert phases[0] == "Observe"
    assert len(candidates) == 3
    assert heuristic_prune([FrameworkParams(max_model_len=1_000_000, max_num_seqs=2)]) == []


def test_standard_mode_uses_progressive_matrix() -> None:
    phases, candidates = plan_candidates(gpu_count=8, max_trials=4, mode="standard")

    assert phases[0] == "StandardMatrix"
    assert [candidate.max_model_len for candidate in candidates] == sorted(
        candidate.max_model_len for candidate in candidates
    )
    assert standard_matrix(gpu_count=8, max_trials=1)[0].max_num_seqs == 1


def test_autoresearch_integration_plan_is_intelligent_mode_only() -> None:
    executor = pi_agent_executor_plan(AgentExecutorSettings())
    plan = autoresearch_integration_plan(executor)

    assert plan["name"] == "Deli_AutoResearch"
    assert plan["scope"] == "intelligent_mode_only"
    assert plan["worker_executor"]["provider"] == "pi"
    assert "heartbeat_watchdog" in plan["protocols"]


def test_pi_agent_worker_prompt_is_bounded() -> None:
    prompt = intelligent_worker_prompt(
        task_spec_path="state/task_spec.md",
        progress_path="state/progress.json",
        directions_path="state/directions_tried.json",
        completion_criteria="write one finding",
    )

    assert "Deli_AutoResearch worker iteration" in prompt
    assert "Do not ask the user questions" in prompt
    assert "one bounded iteration" in prompt


def test_litellm_candidate_provider_validates_structured_output(settings, monkeypatch) -> None:
    class Message:
        content = '{"candidates":[{"gpu_memory_utilization":0.84,"max_num_seqs":64}]}'

    class Choice:
        message = Message()

    class Response:
        choices = [Choice()]

    def fake_completion(**kwargs):
        assert kwargs["response_format"] == {"type": "json_object"}
        return Response()

    monkeypatch.setattr("litellm.completion", fake_completion)
    settings.llm_provider.provider = "openai_compatible"
    settings.llm_provider.model = "openai/gpt-test"

    candidates = LiteLLMCandidateProvider(settings.llm_provider).generate({})

    assert candidates.candidates[0].gpu_memory_utilization == 0.84


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

    assert export_report(report, output_format="markdown").decode() == report
