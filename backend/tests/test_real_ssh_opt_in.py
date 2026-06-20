from __future__ import annotations

import os

import pytest

from inflab.executor import AsyncSSHExecutor, SSHConnectionConfig
from inflab.schemas import CommandRecord


def _real_ssh_target() -> tuple[str, str, int]:
    target = os.environ.get("INFLAB_REAL_SSH_TARGET")
    if not target:
        pytest.skip("set INFLAB_REAL_SSH_TARGET=user@host to run real SSH smoke test")
    port = int(os.environ.get("INFLAB_REAL_SSH_PORT", "22"))
    if "@" in target:
        username, host = target.split("@", 1)
    else:
        username, host = "", target
    return username, host, port


@pytest.mark.asyncio
async def test_real_ssh_agent_read_only_smoke() -> None:
    username, host, port = _real_ssh_target()
    executor = AsyncSSHExecutor(
        SSHConnectionConfig(
            host=host,
            port=port,
            username=username or None,
            credential_type="ssh_agent",
            secret=None,
            known_hosts_policy="permissive",
            connect_timeout_seconds=10,
        )
    )

    result = await executor.run(
        CommandRecord(command="id -un && hostname && uname -srm"),
        timeout_seconds=10,
    )

    assert result.exit_code == 0, result.stderr
    assert result.stdout.strip()
