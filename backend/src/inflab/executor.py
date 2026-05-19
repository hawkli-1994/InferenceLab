"""Remote executor abstractions and fake/local implementations."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Protocol

from inflab.schemas import CommandRecord, CommandResult


@dataclass(slots=True)
class ExecutionContext:
    machine_id: str
    dry_run: bool = True
    artifacts_prefix: str = "memory://artifacts"
    env: dict[str, str] = field(default_factory=dict)


class RemoteExecutor(Protocol):
    async def run(
        self,
        command: CommandRecord,
        *,
        timeout_seconds: int = 30,
    ) -> CommandResult:
        """Run a command on the target."""

    async def upload(self, local_path: str, remote_path: str) -> CommandResult:
        """Upload a file to the target."""

    async def download(self, remote_path: str, local_path: str) -> CommandResult:
        """Download a file from the target."""


class FakeExecutor:
    """Deterministic executor used by default tests and dry-run APIs."""

    def __init__(self) -> None:
        self.commands: list[CommandRecord] = []

    async def run(
        self,
        command: CommandRecord,
        *,
        timeout_seconds: int = 30,
    ) -> CommandResult:
        self.commands.append(command)
        stdout = f"dry-run: {command.command}"
        return CommandResult(command=command, exit_code=0, stdout=stdout, stderr="")

    async def upload(self, local_path: str, remote_path: str) -> CommandResult:
        command = CommandRecord(command=f"upload {local_path} {remote_path}")
        return await self.run(command)

    async def download(self, remote_path: str, local_path: str) -> CommandResult:
        command = CommandRecord(command=f"download {remote_path} {local_path}")
        return await self.run(command)


class LocalExecutor:
    """Local shell executor for development validation only."""

    async def run(
        self,
        command: CommandRecord,
        *,
        timeout_seconds: int = 30,
    ) -> CommandResult:
        process = await asyncio.create_subprocess_shell(
            command.command,
            cwd=command.cwd,
            env=command.env or None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout_seconds)
        return CommandResult(
            command=command,
            exit_code=process.returncode or 0,
            stdout=stdout.decode(errors="replace"),
            stderr=stderr.decode(errors="replace"),
        )

    async def upload(self, local_path: str, remote_path: str) -> CommandResult:
        return await self.run(CommandRecord(command=f"cp {local_path} {remote_path}"))

    async def download(self, remote_path: str, local_path: str) -> CommandResult:
        return await self.run(CommandRecord(command=f"cp {remote_path} {local_path}"))


class AsyncSSHExecutor(FakeExecutor):
    """AsyncSSH-compatible dry-run executor surface.

    The real network implementation is reserved for opt-in E2E and hardware smoke tests. The MVP
    keeps the command/upload/download contract available without opening sockets by default.
    """

    def __init__(self, host: str, port: int = 22) -> None:
        super().__init__()
        self.host = host
        self.port = port

    async def run(
        self,
        command: CommandRecord,
        *,
        timeout_seconds: int = 30,
    ) -> CommandResult:
        wrapped = CommandRecord(
            command=f"asyncssh://{self.host}:{self.port} {command.command}",
            cwd=command.cwd,
            env=command.env,
            sudo=command.sudo,
        )
        return await super().run(wrapped, timeout_seconds=timeout_seconds)
