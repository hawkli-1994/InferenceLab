"""Integration metadata for Deli_AutoResearch-powered intelligent mode."""

from __future__ import annotations

from typing import Any

AUTORESEARCH_SKILL_NAME = "Deli_AutoResearch"


def autoresearch_integration_plan() -> dict[str, Any]:
    return {
        "name": AUTORESEARCH_SKILL_NAME,
        "type": "agent_protocol_framework",
        "scope": "intelligent_mode_only",
        "ships_executable_code": False,
        "role": "long_horizon_orchestration_protocol_for_agent_driven_benchmark_optimization",
        "failure_modes_addressed": [
            "cognitive_loop",
            "stalling",
            "runtime_fragility",
        ],
        "protocols": [
            "state_files",
            "stall_detection",
            "forced_pivot",
            "heartbeat_watchdog",
            "guardian_worker_separation",
            "fresh_session_per_iteration",
            "direction_diversity",
        ],
        "state_layout": {
            "task_spec": "state/task_spec.md",
            "progress": "state/progress.json",
            "findings": "state/findings.jsonl",
            "directions_tried": "state/directions_tried.json",
            "iteration_log": "state/iteration_log.jsonl",
            "work_log": "logs/work.jsonl",
            "orchestrator_log": "logs/orchestrator.jsonl",
            "heartbeat_log": "logs/heartbeat.jsonl",
        },
        "recommended_gates": [
            "uv run pytest",
            "uv run ruff check .",
            "uv run ruff format --check .",
            "pnpm build",
        ],
        "standard_mode_boundary": (
            "standard mode remains deterministic and software-driven; "
            "Deli_AutoResearch is not required"
        ),
    }
