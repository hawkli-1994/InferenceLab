"""Agent executor metadata for intelligent mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from inflab.config import AgentExecutorSettings


@dataclass(frozen=True)
class AgentExecutorPlan:
    provider: str
    command: str
    role: str
    work_dir: str
    max_rounds: int
    timeout_minutes: int
    status: str
    notes: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "command": self.command,
            "role": self.role,
            "work_dir": self.work_dir,
            "max_rounds": self.max_rounds,
            "timeout_minutes": self.timeout_minutes,
            "status": self.status,
            "notes": self.notes,
        }


def pi_agent_executor_plan(settings: AgentExecutorSettings) -> AgentExecutorPlan:
    return AgentExecutorPlan(
        provider=settings.provider,
        command=settings.command,
        role="worker_executor_for_deli_autoresearch_intelligent_mode",
        work_dir=settings.work_dir,
        max_rounds=settings.max_rounds,
        timeout_minutes=settings.timeout_minutes,
        status="configured" if settings.provider == "pi" else "disabled",
        notes=[
            "Pi agent executes one bounded worker iteration; it is not the orchestrator.",
            "Deli_AutoResearch owns state files, stall detection, heartbeat, and pivot rules.",
            "Standard mode never depends on Pi agent.",
            "The Pi command is configurable because installation details are environment-specific.",
        ],
    )


def intelligent_worker_prompt(
    *,
    task_spec_path: str,
    progress_path: str,
    directions_path: str,
    completion_criteria: str,
) -> str:
    return "\n".join(
        [
            "Run one Deli_AutoResearch worker iteration for InferenceLab intelligent mode.",
            f"Read task spec: {task_spec_path}",
            f"Read progress: {progress_path}",
            f"Read tried directions: {directions_path}",
            "Choose a direction that differs structurally from prior directions.",
            "Write findings to state/findings.jsonl.",
            "Write iteration summary to state/iteration_log.jsonl.",
            "Write decisions to logs/work.jsonl with level=decision.",
            f"Completion criteria: {completion_criteria}",
            "Do not ask the user questions. Stop after one bounded iteration.",
        ]
    )
