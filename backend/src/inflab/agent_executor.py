"""Agent executor metadata and bounded Pi workflow execution helpers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from inflab.config import AgentExecutorSettings
from inflab.schemas import CommandRecord, CommandResult

ENVIRONMENT_WORKFLOW_PROMPT_NAME = "inflab_environment_bootstrap_workflow.md"


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


def pi_environment_workflow_plan(settings: AgentExecutorSettings) -> AgentExecutorPlan:
    return AgentExecutorPlan(
        provider=settings.provider,
        command=settings.command,
        role="bounded_executor_for_environment_setup_workflow",
        work_dir=settings.work_dir,
        max_rounds=settings.max_rounds,
        timeout_minutes=settings.timeout_minutes,
        status="configured" if settings.provider == "pi" else "disabled",
        notes=[
            "Pi agent executes a generic environment setup workflow from a task prompt.",
            "The workflow must discover, plan, apply, verify, and record host changes.",
            "Fixed B1-B7 scripts remain only a reproducible scripted baseline.",
            "Standard-mode benchmark planning remains software-driven and does not depend on Pi.",
        ],
    )


def environment_setup_worker_prompt(
    *,
    machine: dict[str, Any],
    profile: str,
    workflow_goal: str,
    dry_run: bool,
) -> str:
    return "\n".join(
        [
            "Execute the InferenceLab environment setup workflow for one target machine.",
            "",
            "Goal:",
            workflow_goal.strip(),
            "",
            "Machine context:",
            f"- name: {machine.get('name', 'unknown')}",
            f"- host: {machine.get('host', 'unknown')}",
            f"- port: {machine.get('port', 'unknown')}",
            f"- username: {machine.get('username', 'unknown')}",
            f"- runtime_mode: {machine.get('runtime_mode', 'both')}",
            f"- bootstrap_profile_context: {profile}",
            f"- dry_run: {dry_run}",
            "",
            "Workflow contract:",
            "1. Discover OS, GPU, driver, CUDA/ROCm, container runtime, Python, storage, "
            "network, package mirrors, permissions, and existing site policy.",
            "2. Produce a concrete plan before changing anything. Prefer minimal, reversible, "
            "idempotent changes and reuse existing mirrors, users, directories, and runtimes.",
            "3. Apply changes only when dry_run is false. Do not assume an Ubuntu-only path; "
            "adapt to the discovered machine state.",
            "4. Verify container and bare-metal inference prerequisites separately when relevant.",
            "5. Record exact commands, versions, changed files, verification evidence, unresolved "
            "blockers, and next manual actions.",
            "6. Do not print or persist secrets. Use preconfigured Pi/SSH access; this prompt does "
            "not include platform credentials.",
            "",
            "Required output:",
            "- JSONL work log with phases discover, plan, apply, verify, record.",
            "- Final readiness verdict: ready, partially_ready, or blocked.",
            "- Failure hints mapped to permission, package source, driver/runtime, storage, "
            "network, or policy blocker.",
        ]
    )


async def run_pi_environment_workflow(
    settings: AgentExecutorSettings,
    prompt: str,
    *,
    dry_run: bool,
) -> CommandResult:
    command = CommandRecord(
        command=f"{settings.command} < {ENVIRONMENT_WORKFLOW_PROMPT_NAME}",
        cwd=settings.work_dir,
    )
    if settings.provider != "pi":
        return CommandResult(
            command=command,
            exit_code=2,
            stdout="",
            stderr="Pi agent is disabled; environment workflow cannot execute.",
        )
    if dry_run:
        return CommandResult(
            command=command,
            exit_code=0,
            stdout=(
                "dry-run: Pi environment workflow prompt prepared; "
                "uncheck dry-run to execute the configured Pi command."
            ),
            stderr="",
        )

    try:
        process = await asyncio.create_subprocess_shell(
            settings.command,
            cwd=settings.work_dir,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(prompt.encode()),
            timeout=settings.timeout_minutes * 60,
        )
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        return CommandResult(
            command=command,
            exit_code=124,
            stdout="",
            stderr=f"Pi environment workflow timed out after {settings.timeout_minutes}m: {exc}",
        )
    except OSError as exc:
        return CommandResult(command=command, exit_code=127, stdout="", stderr=str(exc))

    return CommandResult(
        command=command,
        exit_code=process.returncode or 0,
        stdout=stdout.decode(errors="replace"),
        stderr=stderr.decode(errors="replace"),
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
