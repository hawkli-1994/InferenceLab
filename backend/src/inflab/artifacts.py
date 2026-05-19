"""Artifact and model-distribution helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path


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
        "nfs": f"mount reference path {cache_path}",
        "minio": f"presign s3 object for {cache_path}",
        "huggingface": f"mock download from HuggingFace into {cache_path}",
        "modelscope": f"mock download from ModelScope into {cache_path}",
        "mock": f"mock model already available at {cache_path}",
    }
    return {"source": source, "plan": plans.get(source, plans["mock"])}
