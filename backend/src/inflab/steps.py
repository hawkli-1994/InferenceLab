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
        apply_command=(
            "id inflab >/dev/null 2>&1 || useradd -m inflab; "
            "install -d -m 700 -o inflab -g inflab /home/inflab/.ssh; "
            "printf 'inflab ALL=(ALL) NOPASSWD:ALL\\n' > /etc/sudoers.d/inflab; "
            "chmod 440 /etc/sudoers.d/inflab"
        ),
        verify_command="test -d /home/inflab/.ssh",
        changed_files=["/etc/sudoers.d/inflab", "/home/inflab/.ssh/authorized_keys"],
        snapshot_keys=["sshd_config", "users"],
        failure_hint="Check SSH credentials and sudo permissions.",
    ),
    "B2": ShellRemoteStep(
        id="B2",
        name="Source Bootstrap",
        detect_command="test -f /etc/apt/sources.list || true",
        apply_command=(
            "install -d /etc/pip.conf.d /etc/docker; "
            "printf '[global]\\ntimeout = 60\\nretries = 5\\n' > /etc/pip.conf; "
            "touch /etc/apt/sources.list; "
            'printf \'{"features":{"buildkit":true}}\\n\' > /etc/docker/daemon.json'
        ),
        verify_command="test -f /etc/apt/sources.list",
        changed_files=["/etc/apt/sources.list", "/etc/docker/daemon.json"],
        snapshot_keys=["sources"],
        failure_hint="Check mirror URLs and network reachability.",
    ),
    "B3": ShellRemoteStep(
        id="B3",
        name="Package Bootstrap",
        detect_command="command -v jq && command -v rsync || true",
        apply_command=(
            "export DEBIAN_FRONTEND=noninteractive; "
            "apt-get update && apt-get install -y "
            "jq rsync curl git python3 python3-venv python3-pip"
        ),
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
        apply_command=(
            "install -d /etc/docker; "
            'printf \'{"features":{"buildkit":true},"default-runtime":"nvidia",'
            '"runtimes":{"nvidia":{"path":"nvidia-container-runtime","runtimeArgs":[]}}}\\n\' '
            "> /etc/docker/daemon.json; "
            "systemctl restart docker || true"
        ),
        verify_command="test -f /etc/docker/daemon.json",
        changed_files=["/etc/docker/daemon.json"],
        snapshot_keys=["docker_info"],
        failure_hint="Check Docker installation or dry-run runtime settings.",
    ),
    "B6": ShellRemoteStep(
        id="B6",
        name="Baseline Tuning Record",
        detect_command="sysctl -a | head || true",
        apply_command=(
            "install -d /data/logs; "
            "sysctl -a > /data/logs/inflab-sysctl-baseline.txt 2>/dev/null || true; "
            "ulimit -a > /data/logs/inflab-ulimit-baseline.txt || true"
        ),
        verify_command="test -f /data/logs/inflab-sysctl-baseline.txt",
        changed_files=[
            "/data/logs/inflab-sysctl-baseline.txt",
            "/data/logs/inflab-ulimit-baseline.txt",
        ],
        snapshot_keys=["sysctl_baseline"],
        failure_hint="Check host sysctl read permissions.",
    ),
    "B7": ShellRemoteStep(
        id="B7",
        name="Bare-Metal Runtime Bootstrap",
        detect_command="python3 --version || true",
        apply_command=(
            "mkdir -p /data/workspace; "
            "test -d /data/workspace/inflab-venv || python3 -m venv /data/workspace/inflab-venv; "
            "/data/workspace/inflab-venv/bin/python -m pip install -U pip wheel"
        ),
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
