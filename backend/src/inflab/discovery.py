"""Safe read-only environment discovery workflow."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from inflab.artifacts import sha256_text
from inflab.executor import RemoteExecutor
from inflab.probe import parse_nvidia_smi_csv
from inflab.schemas import CommandRecord, CommandResult

DiscoveryVerdict = Literal["ready", "partially_ready", "blocked"]
BlockerSeverity = Literal["warning", "blocking"]


@dataclass(frozen=True, slots=True)
class DiscoveryCommand:
    id: str
    name: str
    command: str
    timeout_seconds: int = 15
    required: bool = False


SAFE_DISCOVERY_COMMANDS: tuple[DiscoveryCommand, ...] = (
    DiscoveryCommand(
        id="identity",
        name="Identity and kernel",
        command="id -un && hostname && uname -srm",
        required=True,
    ),
    DiscoveryCommand(
        id="os_release",
        name="OS release",
        command="cat /etc/os-release",
    ),
    DiscoveryCommand(
        id="cpu",
        name="CPU topology",
        command="lscpu -J",
    ),
    DiscoveryCommand(
        id="memory",
        name="Memory",
        command="awk '/MemTotal/ {print $2}' /proc/meminfo",
    ),
    DiscoveryCommand(
        id="gpu",
        name="NVIDIA GPU",
        command=(
            "nvidia-smi --query-gpu=index,name,memory.total,driver_version,cuda_version "
            "--format=csv,noheader,nounits"
        ),
    ),
    DiscoveryCommand(
        id="python",
        name="Python runtime",
        command="python3 --version",
    ),
    DiscoveryCommand(
        id="docker",
        name="Docker runtime",
        command="docker info --format '{{json .}}'",
    ),
    DiscoveryCommand(
        id="storage",
        name="Storage",
        command="df -P / /data",
    ),
    DiscoveryCommand(
        id="network",
        name="Network interfaces",
        command="ip -json addr",
    ),
)


def discovery_allowlist() -> list[dict[str, Any]]:
    return [
        {
            "id": command.id,
            "name": command.name,
            "command": command.command,
            "required": command.required,
            "timeout_seconds": command.timeout_seconds,
        }
        for command in SAFE_DISCOVERY_COMMANDS
    ]


def _json_or_raw(value: str) -> Any:
    value = value.strip()
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _parse_os_release(value: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in value.splitlines():
        if "=" not in line:
            continue
        key, raw = line.split("=", 1)
        parsed[key] = raw.strip().strip('"')
    return parsed


def _command_result(results: dict[str, CommandResult], command_id: str) -> CommandResult | None:
    return results.get(command_id)


def _stdout(results: dict[str, CommandResult], command_id: str) -> str:
    result = _command_result(results, command_id)
    if result is None or result.exit_code != 0:
        return ""
    return result.stdout


def _result_failed(results: dict[str, CommandResult], command_id: str) -> bool:
    result = _command_result(results, command_id)
    return result is None or result.exit_code != 0


def _memory_gb(value: str) -> float | None:
    stripped = value.strip()
    if not stripped.isdigit():
        return None
    return round(int(stripped) / 1024 / 1024, 2)


def _identity(value: str) -> dict[str, str]:
    user, hostname, kernel = [*value.splitlines(), "", "", ""][:3]
    return {"user": user, "hostname": hostname, "kernel": kernel}


def _machine_key(machine: dict[str, Any]) -> str:
    raw = str(machine.get("id") or machine.get("host") or "unknown")
    return "".join(
        character if character.isalnum() or character in ".-" else "_" for character in raw
    )


def _attach_artifact_uris(
    result: CommandResult,
    *,
    machine: dict[str, Any],
    command_id: str,
) -> CommandResult:
    prefix = f"memory://discovery/{_machine_key(machine)}/{command_id}"
    return result.model_copy(
        update={
            "stdout_uri": f"{prefix}/stdout.txt",
            "stderr_uri": f"{prefix}/stderr.txt",
        }
    )


def build_discovery_profile(
    *,
    machine: dict[str, Any],
    command_results: dict[str, CommandResult],
) -> dict[str, Any]:
    docker_stdout = _stdout(command_results, "docker")
    storage_stdout = _stdout(command_results, "storage")
    profile = {
        "host": machine["host"],
        "port": machine["port"],
        "username": machine["username"],
        "runtime_mode": machine["runtime_mode"],
        "access_mode": "safe_discovery",
        "discovery_version": "safe-readonly-v1",
        "identity": _identity(_stdout(command_results, "identity")),
        "system": {
            "os_release": _parse_os_release(_stdout(command_results, "os_release")),
        },
        "hardware": {
            "cpu": _json_or_raw(_stdout(command_results, "cpu")),
            "memory_gb": _memory_gb(_stdout(command_results, "memory")),
            "gpu": parse_nvidia_smi_csv(_stdout(command_results, "gpu")),
        },
        "runtime": {
            "python": _stdout(command_results, "python").strip(),
            "docker_available": bool(docker_stdout.strip()),
            "docker_info": _json_or_raw(docker_stdout),
        },
        "storage": {
            "data_path_available": "/data" in storage_stdout,
            "df": storage_stdout,
        },
        "network": {
            "interfaces": _json_or_raw(_stdout(command_results, "network")),
        },
    }
    profile["fingerprint"] = sha256_text(json.dumps(profile, sort_keys=True, default=str))
    return profile


def evaluate_discovery(
    *,
    runtime_mode: str,
    profile: dict[str, Any],
    command_results: dict[str, CommandResult],
) -> tuple[DiscoveryVerdict, list[dict[str, str]]]:
    blockers: list[dict[str, str]] = []
    for command in SAFE_DISCOVERY_COMMANDS:
        if command.required and _result_failed(command_results, command.id):
            blockers.append(
                {
                    "key": f"{command.id}_failed",
                    "severity": "blocking",
                    "message": f"Required read-only discovery command failed: {command.name}.",
                    "evidence_command": command.id,
                }
            )

    if not profile["hardware"]["gpu"]:
        blockers.append(
            {
                "key": "gpu_unavailable",
                "severity": "blocking",
                "message": "No NVIDIA GPU was discovered through nvidia-smi.",
                "evidence_command": "gpu",
            }
        )

    if not profile["runtime"]["python"]:
        blockers.append(
            {
                "key": "python_unavailable",
                "severity": "blocking",
                "message": "python3 is unavailable or not visible to the SSH user.",
                "evidence_command": "python",
            }
        )

    if runtime_mode in {"container", "both"} and not profile["runtime"]["docker_available"]:
        severity: BlockerSeverity = "blocking" if runtime_mode == "container" else "warning"
        blockers.append(
            {
                "key": "container_runtime_unavailable",
                "severity": severity,
                "message": "Docker is unavailable or inaccessible to the SSH user.",
                "evidence_command": "docker",
            }
        )

    if not profile["storage"]["data_path_available"]:
        blockers.append(
            {
                "key": "data_path_missing",
                "severity": "warning",
                "message": "/data is not visible in df output; model/cache paths may need review.",
                "evidence_command": "storage",
            }
        )

    if any(blocker["severity"] == "blocking" for blocker in blockers):
        return "blocked", blockers
    if blockers:
        return "partially_ready", blockers
    return "ready", blockers


async def run_safe_environment_discovery(
    *,
    machine: dict[str, Any],
    executor: RemoteExecutor,
) -> dict[str, Any]:
    command_results: dict[str, CommandResult] = {}
    for command in SAFE_DISCOVERY_COMMANDS:
        result = await executor.run(
            CommandRecord(command=command.command, sudo=False),
            timeout_seconds=command.timeout_seconds,
        )
        command_results[command.id] = _attach_artifact_uris(
            result,
            machine=machine,
            command_id=command.id,
        )

    profile = build_discovery_profile(machine=machine, command_results=command_results)
    verdict, blockers = evaluate_discovery(
        runtime_mode=machine["runtime_mode"],
        profile=profile,
        command_results=command_results,
    )
    return {
        "verdict": verdict,
        "blockers": blockers,
        "profile": profile,
        "command_results": command_results,
        "allowlist": discovery_allowlist(),
    }


def fake_safe_environment_discovery(machine: dict[str, Any]) -> dict[str, Any]:
    command_results = {
        "identity": _attach_artifact_uris(
            CommandResult(
                command=CommandRecord(command="id -un && hostname && uname -srm"),
                exit_code=0,
                stdout=f"{machine['username']}\n{machine['host']}\nLinux mock x86_64\n",
            ),
            machine=machine,
            command_id="identity",
        ),
        "os_release": _attach_artifact_uris(
            CommandResult(
                command=CommandRecord(command="cat /etc/os-release"),
                exit_code=0,
                stdout='ID=ubuntu\nVERSION_ID="24.04"\n',
            ),
            machine=machine,
            command_id="os_release",
        ),
        "cpu": _attach_artifact_uris(
            CommandResult(
                command=CommandRecord(command="lscpu -J"),
                exit_code=0,
                stdout='{"lscpu":[{"field":"Model name:","data":"MockCPU"}]}',
            ),
            machine=machine,
            command_id="cpu",
        ),
        "memory": _attach_artifact_uris(
            CommandResult(
                command=CommandRecord(command="awk '/MemTotal/ {print $2}' /proc/meminfo"),
                exit_code=0,
                stdout="536870912\n",
            ),
            machine=machine,
            command_id="memory",
        ),
        "gpu": _attach_artifact_uris(
            CommandResult(
                command=CommandRecord(command=SAFE_DISCOVERY_COMMANDS[4].command),
                exit_code=0,
                stdout="0, MockGPU, 81920, 555.55, 12.4\n",
            ),
            machine=machine,
            command_id="gpu",
        ),
        "python": _attach_artifact_uris(
            CommandResult(
                command=CommandRecord(command="python3 --version"),
                exit_code=0,
                stdout="Python 3.12.0\n",
            ),
            machine=machine,
            command_id="python",
        ),
        "docker": _attach_artifact_uris(
            CommandResult(
                command=CommandRecord(command="docker info --format '{{json .}}'"),
                exit_code=0,
                stdout='{"ServerVersion":"dry-run"}',
            ),
            machine=machine,
            command_id="docker",
        ),
        "storage": _attach_artifact_uris(
            CommandResult(
                command=CommandRecord(command="df -P / /data"),
                exit_code=0,
                stdout=(
                    "Filesystem 1024-blocks Used Available Capacity Mounted on\n"
                    "mock 1 0 1 0% /data\n"
                ),
            ),
            machine=machine,
            command_id="storage",
        ),
        "network": _attach_artifact_uris(
            CommandResult(
                command=CommandRecord(command="ip -json addr"),
                exit_code=0,
                stdout="[]",
            ),
            machine=machine,
            command_id="network",
        ),
    }
    profile = build_discovery_profile(machine=machine, command_results=command_results)
    verdict, blockers = evaluate_discovery(
        runtime_mode=machine["runtime_mode"],
        profile=profile,
        command_results=command_results,
    )
    return {
        "verdict": verdict,
        "blockers": blockers,
        "profile": profile,
        "command_results": command_results,
        "allowlist": discovery_allowlist(),
    }
