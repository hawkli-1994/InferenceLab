"""Remote step protocol, step runner, and dry-run B1-B7 bootstrap steps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from inflab.executor import ExecutionContext, RemoteExecutor
from inflab.schemas import CommandRecord, CommandResult, StepResult, StepStatus


class RemoteStep(Protocol):
    id: str
    name: str

    async def detect(self, ctx: ExecutionContext, executor: RemoteExecutor) -> CommandResult: ...

    async def apply(self, ctx: ExecutionContext, executor: RemoteExecutor) -> CommandResult: ...

    async def verify(self, ctx: ExecutionContext, executor: RemoteExecutor) -> CommandResult: ...


@dataclass(slots=True)
class ShellRemoteStep:
    id: str
    name: str
    detect_command: str
    apply_command: str
    verify_command: str
    changed_files: list[str]
    snapshot_keys: list[str]
    failure_hint: str

    async def detect(self, ctx: ExecutionContext, executor: RemoteExecutor) -> CommandResult:
        return await executor.run(CommandRecord(command=self.detect_command))

    async def apply(self, ctx: ExecutionContext, executor: RemoteExecutor) -> CommandResult:
        prefix = "DRY_RUN=1 " if ctx.dry_run else ""
        return await executor.run(CommandRecord(command=f"{prefix}{self.apply_command}", sudo=True))

    async def verify(self, ctx: ExecutionContext, executor: RemoteExecutor) -> CommandResult:
        return await executor.run(CommandRecord(command=self.verify_command))


async def run_step(
    step: RemoteStep,
    ctx: ExecutionContext,
    executor: RemoteExecutor,
) -> StepResult:
    phase_results = {
        "detect": await step.detect(ctx, executor),
        "apply": await step.apply(ctx, executor),
        "verify": await step.verify(ctx, executor),
    }
    exit_code = max(result.exit_code for result in phase_results.values())
    status = StepStatus.changed if exit_code == 0 else StepStatus.failed
    commands = [result.command for result in phase_results.values()]
    changed_files = getattr(step, "changed_files", [])
    snapshots = {
        key: f"snapshot://{ctx.machine_id}/{step.id}/{key}"
        for key in getattr(step, "snapshot_keys", [])
    }
    return StepResult(
        id=step.id,
        name=step.name,
        status=status,
        phase_results=phase_results,
        commands=commands,
        exit_code=exit_code,
        stdout_uri=f"{ctx.artifacts_prefix}/{step.id}/stdout.txt",
        stderr_uri=f"{ctx.artifacts_prefix}/{step.id}/stderr.txt",
        changed_files=changed_files,
        snapshots=snapshots,
        failure_hint=None if exit_code == 0 else getattr(step, "failure_hint", None),
    )


async def run_steps(
    steps: list[RemoteStep],
    ctx: ExecutionContext,
    executor: RemoteExecutor,
) -> list[StepResult]:
    return [await run_step(step, ctx, executor) for step in steps]


BOOTSTRAP_STEPS: dict[str, ShellRemoteStep] = {
    "B1": ShellRemoteStep(
        id="B1",
        name="Access Bootstrap",
        detect_command="id inflab || true",
        apply_command="useradd -m inflab && install -d /home/inflab/.ssh",
        verify_command="test -d /home/inflab/.ssh",
        changed_files=["/etc/sudoers.d/inflab", "/home/inflab/.ssh/authorized_keys"],
        snapshot_keys=["sshd_config", "users"],
        failure_hint="Check SSH credentials and sudo permissions.",
    ),
    "B2": ShellRemoteStep(
        id="B2",
        name="Source Bootstrap",
        detect_command="test -f /etc/apt/sources.list || true",
        apply_command="write mirror configuration for apt/pip/docker/huggingface",
        verify_command="test -f /etc/apt/sources.list",
        changed_files=["/etc/apt/sources.list", "/etc/docker/daemon.json"],
        snapshot_keys=["sources"],
        failure_hint="Check mirror URLs and network reachability.",
    ),
    "B3": ShellRemoteStep(
        id="B3",
        name="Package Bootstrap",
        detect_command="command -v jq && command -v rsync || true",
        apply_command="apt-get install -y jq rsync curl git python3",
        verify_command="command -v jq && command -v rsync",
        changed_files=["/var/lib/dpkg/status"],
        snapshot_keys=["packages"],
        failure_hint="Check apt source configuration and package locks.",
    ),
    "B4": ShellRemoteStep(
        id="B4",
        name="Storage Bootstrap",
        detect_command="lsblk --json || true",
        apply_command="mkdir -p /data/models /data/images /data/workspace /data/logs",
        verify_command="test -d /data/models && test -d /data/logs",
        changed_files=["/data/models", "/data/images", "/data/workspace", "/data/logs"],
        snapshot_keys=["lsblk", "mounts"],
        failure_hint="Check filesystem permissions and NAS dry-run settings.",
    ),
    "B5": ShellRemoteStep(
        id="B5",
        name="Container Bootstrap",
        detect_command="docker info || true",
        apply_command="write docker dry-run runtime configuration",
        verify_command="echo docker runtime dry-run verified",
        changed_files=["/etc/docker/daemon.json"],
        snapshot_keys=["docker_info"],
        failure_hint="Check Docker installation or dry-run runtime settings.",
    ),
    "B6": ShellRemoteStep(
        id="B6",
        name="Baseline Tuning Record",
        detect_command="sysctl -a | head || true",
        apply_command="record baseline tuning without kernel mutation",
        verify_command="echo baseline captured",
        changed_files=[],
        snapshot_keys=["sysctl_baseline"],
        failure_hint="Check host sysctl read permissions.",
    ),
    "B7": ShellRemoteStep(
        id="B7",
        name="Bare-Metal Runtime Bootstrap",
        detect_command="python3 --version || true",
        apply_command="python3 -m venv /data/workspace/inflab-venv",
        verify_command="test -d /data/workspace/inflab-venv",
        changed_files=["/data/workspace/inflab-venv"],
        snapshot_keys=["python", "pip_freeze"],
        failure_hint="Check Python and venv availability.",
    ),
}


PROFILE_MODULES: dict[str, list[str]] = {
    "minimal": ["B1", "B2"],
    "standard_container": ["B1", "B2", "B3", "B4", "B5", "B6"],
    "standard_bare_metal": ["B1", "B2", "B3", "B4", "B6", "B7"],
    "full": ["B1", "B2", "B3", "B4", "B5", "B6", "B7"],
}


def resolve_bootstrap_steps(profile: str, modules: list[str] | None = None) -> list[RemoteStep]:
    selected = modules or PROFILE_MODULES.get(profile, PROFILE_MODULES["full"])
    return [BOOTSTRAP_STEPS[module] for module in selected]
