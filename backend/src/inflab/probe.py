"""Remote machine probing through the executor abstraction."""

from __future__ import annotations

import json
from typing import Any

from inflab.artifacts import sha256_text
from inflab.executor import RemoteExecutor
from inflab.schemas import CommandRecord


async def _run_probe_command(
    executor: RemoteExecutor,
    command: str,
    *,
    timeout_seconds: int = 30,
) -> str:
    result = await executor.run(CommandRecord(command=command), timeout_seconds=timeout_seconds)
    return result.stdout if result.exit_code == 0 else ""


def _json_or_raw(value: str) -> Any:
    value = value.strip()
    if not value:
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def parse_nvidia_smi_csv(value: str) -> list[dict[str, Any]]:
    rows = []
    for line in value.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 5:
            continue
        index, name, memory_total, driver_version, cuda_version = parts[:5]
        rows.append(
            {
                "index": int(index) if index.isdigit() else index,
                "vendor": "nvidia",
                "model": name,
                "memory_mb": float(memory_total)
                if memory_total.replace(".", "", 1).isdigit()
                else memory_total,
                "driver_version": driver_version,
                "cuda_version": cuda_version,
            }
        )
    return rows


async def probe_remote_machine(
    executor: RemoteExecutor, *, host: str, runtime_mode: str
) -> dict[str, Any]:
    lscpu = _json_or_raw(await _run_probe_command(executor, "lscpu -J || true"))
    lsblk = _json_or_raw(await _run_probe_command(executor, "lsblk --json || true"))
    docker = _json_or_raw(
        await _run_probe_command(executor, "docker info --format '{{json .}}' || true")
    )
    network = _json_or_raw(await _run_probe_command(executor, "ip -json addr || true"))
    disk = await _run_probe_command(executor, "df -P / /data 2>/dev/null || df -P / || true")
    gpu_csv = await _run_probe_command(
        executor,
        "nvidia-smi --query-gpu=index,name,memory.total,driver_version,cuda_version "
        "--format=csv,noheader,nounits || true",
    )
    uname = await _run_probe_command(executor, "uname -a || true")

    profile = {
        "host": host,
        "runtime_mode": runtime_mode,
        "access_mode": "ssh",
        "hardware": {
            "cpu": lscpu,
            "gpu": parse_nvidia_smi_csv(gpu_csv),
        },
        "system": {"uname": uname.strip()},
        "container": docker,
        "network": network,
        "storage": {"lsblk": lsblk, "df": disk},
    }
    profile["fingerprint"] = sha256_text(json.dumps(profile, sort_keys=True, default=str))
    return profile
