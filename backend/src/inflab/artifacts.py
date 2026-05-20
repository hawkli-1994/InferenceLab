"""Artifact and model-distribution helpers."""

from __future__ import annotations

import hashlib
import shlex
from pathlib import Path

from inflab.executor import RemoteExecutor
from inflab.schemas import CommandRecord


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def distribution_plan(source: str, cache_path: str) -> dict[str, str]:
    plans = {
        "rsync": f"rsync --partial --checksum {cache_path} target:{cache_path}",
        "nfs": f"test -d {cache_path} on mounted NFS path",
        "minio": f"aws s3 sync object prefix into {cache_path}",
        "huggingface": f"huggingface-cli download into {cache_path}",
        "modelscope": f"modelscope download into {cache_path}",
        "mock": f"model already available at {cache_path}",
    }
    return {"source": source, "plan": plans.get(source, plans["mock"])}


def model_distribution_command(source: str, cache_path: str, target_path: str) -> str:
    quoted_cache = shlex.quote(cache_path)
    quoted_target = shlex.quote(target_path)
    if source == "rsync":
        return (
            f"mkdir -p {quoted_target} && "
            f"rsync -a --partial --checksum {quoted_cache}/ {quoted_target}/"
        )
    if source == "nfs":
        return (
            f"test -d {quoted_cache} && "
            f"mkdir -p {quoted_target} && "
            f"ln -sfn {quoted_cache} {quoted_target}"
        )
    if source == "minio":
        return f"mkdir -p {quoted_target} && aws s3 sync {quoted_cache} {quoted_target}"
    if source == "huggingface":
        return (
            "mkdir -p "
            f"{quoted_target} && "
            f"huggingface-cli download {quoted_cache} --local-dir {quoted_target} "
            "--resume-download"
        )
    if source == "modelscope":
        return (
            f"mkdir -p {quoted_target} && "
            f"modelscope download --model {quoted_cache} --local_dir {quoted_target}"
        )
    return f"test -e {quoted_cache}"


async def distribute_model(
    executor: RemoteExecutor,
    *,
    source: str,
    cache_path: str,
    target_path: str,
    expected_sha256: str | None = None,
) -> dict[str, object]:
    command = model_distribution_command(source, cache_path, target_path)
    result = await executor.run(CommandRecord(command=command), timeout_seconds=3600)
    verify_command = f"test -e {shlex.quote(target_path)}"
    if expected_sha256:
        verify_command = (
            f"find {shlex.quote(target_path)} -type f -print0 | sort -z | "
            "xargs -0 sha256sum | sha256sum"
        )
    verify = await executor.run(CommandRecord(command=verify_command), timeout_seconds=600)
    return {
        "command": result.command.command,
        "exit_code": result.exit_code,
        "verify_command": verify.command.command,
        "verify_exit_code": verify.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "expected_sha256": expected_sha256,
    }
