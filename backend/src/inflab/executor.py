"""Remote executor abstractions and local/SSH implementations."""

from __future__ import annotations

import asyncio
import re
import shlex
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

import asyncssh

from inflab.schemas import CommandRecord, CommandResult


@dataclass(slots=True)
class ExecutionContext:
    machine_id: str
    dry_run: bool = True
    artifacts_prefix: str = "memory://artifacts"
    env: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class SSHConnectionConfig:
    host: str
    port: int = 22
    username: str | None = None
    credential_type: str = "password"
    secret: str | None = None
    known_hosts_policy: str = "permissive"
    connect_timeout_seconds: int = 30


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

    async def stream(
        self,
        command: CommandRecord,
        *,
        on_line: Callable[[str], None],
        timeout_seconds: int = 30,
    ) -> CommandResult:
        """Run a command and emit stdout/stderr lines as they arrive."""


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

    async def stream(
        self,
        command: CommandRecord,
        *,
        on_line: Callable[[str], None],
        timeout_seconds: int = 30,
    ) -> CommandResult:
        result = await self.run(command, timeout_seconds=timeout_seconds)
        for line in [*result.stdout.splitlines(), *result.stderr.splitlines()]:
            on_line(line)
        return result


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

    async def stream(
        self,
        command: CommandRecord,
        *,
        on_line: Callable[[str], None],
        timeout_seconds: int = 30,
    ) -> CommandResult:
        result = await self.run(command, timeout_seconds=timeout_seconds)
        for line in [*result.stdout.splitlines(), *result.stderr.splitlines()]:
            on_line(line)
        return result


_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_env_prefix(env: dict[str, str]) -> str:
    assignments = []
    for name, value in env.items():
        if not _ENV_NAME.match(name):
            raise ValueError(f"Invalid remote environment variable name: {name}")
        assignments.append(f"{name}={shlex.quote(value)}")
    return " ".join(assignments)


def _remote_shell_command(command: CommandRecord) -> str:
    remote_command = command.command
    if command.env:
        remote_command = f"env {_safe_env_prefix(command.env)} {remote_command}"
    if command.cwd:
        remote_command = f"cd {shlex.quote(command.cwd)} && {remote_command}"
    if command.sudo:
        remote_command = f"sudo -n -- sh -lc {shlex.quote(remote_command)}"
    return remote_command


class AsyncSSHExecutor:
    """Real AsyncSSH executor used only by explicit opt-in runtime paths."""

    def __init__(
        self,
        config: SSHConnectionConfig | None = None,
        *,
        host: str | None = None,
        port: int = 22,
        username: str | None = None,
        credential_type: str = "password",
        secret: str | None = None,
        known_hosts_policy: str = "permissive",
        connect_timeout_seconds: int = 30,
    ) -> None:
        self.config = config or SSHConnectionConfig(
            host=host or "",
            port=port,
            username=username,
            credential_type=credential_type,
            secret=secret,
            known_hosts_policy=known_hosts_policy,
            connect_timeout_seconds=connect_timeout_seconds,
        )
        self._client_keys: list[object] | None = None

    def _connect_kwargs(self) -> dict[str, object]:
        kwargs: dict[str, object] = {
            "port": self.config.port,
            "username": self.config.username,
            "connect_timeout": self.config.connect_timeout_seconds,
        }
        if self.config.known_hosts_policy == "permissive":
            kwargs["known_hosts"] = None
        if self.config.secret:
            if self.config.credential_type == "private_key":
                if self._client_keys is None:
                    key_material = self.config.secret.encode()
                    self._client_keys = [asyncssh.import_private_key(key_material)]
                kwargs["client_keys"] = self._client_keys
            else:
                kwargs["password"] = self.config.secret
        return {
            key: value for key, value in kwargs.items() if value is not None or key == "known_hosts"
        }

    def _connection(self):
        if not self.config.host:
            raise ValueError("SSH host is required")
        return asyncssh.connect(self.config.host, **self._connect_kwargs())

    async def run(
        self,
        command: CommandRecord,
        *,
        timeout_seconds: int = 30,
    ) -> CommandResult:
        try:
            remote_command = _remote_shell_command(command)
            executed = CommandRecord(
                command=remote_command,
                cwd=command.cwd,
                env=command.env,
                sudo=command.sudo,
            )
            async with self._connection() as conn:
                result = await conn.run(remote_command, check=False, timeout=timeout_seconds)
        except asyncssh.TimeoutError as exc:
            return CommandResult(
                command=executed,
                exit_code=124,
                stdout="",
                stderr=f"SSH command timed out after {timeout_seconds}s: {exc}",
            )
        except (OSError, asyncssh.Error, ValueError) as exc:
            return CommandResult(command=command, exit_code=255, stdout="", stderr=str(exc))

        exit_code = result.exit_status if result.exit_status is not None else 255
        stderr = result.stderr or ""
        if result.exit_signal:
            stderr = f"{stderr}\nexit signal: {result.exit_signal}".strip()
        return CommandResult(
            command=executed,
            exit_code=exit_code,
            stdout=result.stdout or "",
            stderr=stderr,
        )

    async def upload(self, local_path: str, remote_path: str) -> CommandResult:
        command = CommandRecord(command=f"sftp put {local_path} {remote_path}")
        try:
            async with self._connection() as conn, conn.start_sftp_client() as sftp:
                await sftp.put(local_path, remote_path)
        except (OSError, asyncssh.Error, ValueError) as exc:
            return CommandResult(command=command, exit_code=255, stdout="", stderr=str(exc))
        return CommandResult(command=command, exit_code=0, stdout=f"uploaded {local_path}")

    async def download(self, remote_path: str, local_path: str) -> CommandResult:
        command = CommandRecord(command=f"sftp get {remote_path} {local_path}")
        try:
            async with self._connection() as conn, conn.start_sftp_client() as sftp:
                await sftp.get(remote_path, local_path)
        except (OSError, asyncssh.Error, ValueError) as exc:
            return CommandResult(command=command, exit_code=255, stdout="", stderr=str(exc))
        return CommandResult(command=command, exit_code=0, stdout=f"downloaded {remote_path}")

    async def stream(
        self,
        command: CommandRecord,
        *,
        on_line: Callable[[str], None],
        timeout_seconds: int = 30,
    ) -> CommandResult:
        remote_command = _remote_shell_command(command)
        executed = CommandRecord(
            command=remote_command,
            cwd=command.cwd,
            env=command.env,
            sudo=command.sudo,
        )
        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        async def read_lines(reader: object, sink: list[str]) -> None:
            async for line in reader:  # type: ignore[union-attr]
                text = str(line).rstrip("\r\n")
                sink.append(text)
                on_line(text)

        try:
            async with self._connection() as conn:
                process = await conn.create_process(remote_command, encoding="utf-8")
                stdout_task = asyncio.create_task(read_lines(process.stdout, stdout_lines))
                stderr_task = asyncio.create_task(read_lines(process.stderr, stderr_lines))
                try:
                    await asyncio.wait_for(process.wait_closed(), timeout=timeout_seconds)
                    await asyncio.gather(stdout_task, stderr_task)
                except TimeoutError as exc:
                    process.kill()
                    await process.wait_closed()
                    stdout_task.cancel()
                    stderr_task.cancel()
                    return CommandResult(
                        command=executed,
                        exit_code=124,
                        stdout="\n".join(stdout_lines),
                        stderr=(
                            "\n".join(stderr_lines)
                            + f"\nSSH command timed out after {timeout_seconds}s: {exc}"
                        ).strip(),
                    )
        except (OSError, asyncssh.Error, ValueError) as exc:
            return CommandResult(command=command, exit_code=255, stdout="", stderr=str(exc))

        exit_code = process.exit_status
        if exit_code is None:
            exit_code = getattr(process, "returncode", None)
        if exit_code is None:
            exit_code = 255
        stderr = "\n".join(stderr_lines)
        if process.exit_signal:
            stderr = f"{stderr}\nexit signal: {process.exit_signal}".strip()
        return CommandResult(
            command=executed,
            exit_code=exit_code,
            stdout="\n".join(stdout_lines),
            stderr=stderr,
        )
