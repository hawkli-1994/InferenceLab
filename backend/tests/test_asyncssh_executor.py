from __future__ import annotations

from dataclasses import dataclass

import pytest

from inflab.executor import AsyncSSHExecutor, SSHConnectionConfig
from inflab.schemas import CommandRecord


@dataclass
class FakeSSHResult:
    stdout: str = "ok"
    stderr: str = ""
    exit_status: int | None = 0
    exit_signal: str | None = None


class FakeSFTP:
    def __init__(self) -> None:
        self.puts: list[tuple[str, str]] = []
        self.gets: list[tuple[str, str]] = []

    async def __aenter__(self) -> FakeSFTP:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def put(self, local_path: str, remote_path: str) -> None:
        self.puts.append((local_path, remote_path))

    async def get(self, remote_path: str, local_path: str) -> None:
        self.gets.append((remote_path, local_path))


class FakeConnection:
    def __init__(self) -> None:
        self.runs: list[dict[str, object]] = []
        self.processes: list[dict[str, object]] = []
        self.sftp = FakeSFTP()

    async def run(
        self,
        command: str,
        *,
        check: bool,
        timeout: int,
    ) -> FakeSSHResult:
        self.runs.append({"command": command, "check": check, "timeout": timeout})
        return FakeSSHResult(stdout="remote-ok")

    def start_sftp_client(self) -> FakeSFTP:
        return self.sftp

    async def create_process(self, command: str, *, encoding: str) -> FakeProcess:
        self.processes.append({"command": command, "encoding": encoding})
        return FakeProcess(stdout=["line-1\n", "line-2\n"], stderr=["warn\n"])


class FakeReader:
    def __init__(self, lines: list[str]) -> None:
        self.lines = lines

    def __aiter__(self) -> FakeReader:
        return self

    async def __anext__(self) -> str:
        if not self.lines:
            raise StopAsyncIteration
        return self.lines.pop(0)


class FakeProcess:
    def __init__(self, *, stdout: list[str], stderr: list[str]) -> None:
        self.stdout = FakeReader(stdout)
        self.stderr = FakeReader(stderr)
        self.exit_status = 0
        self.exit_signal = None
        self.returncode = 0
        self.killed = False

    async def wait_closed(self) -> None:
        return None

    def kill(self) -> None:
        self.killed = True


class FakeConnectContext:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def __aenter__(self) -> FakeConnection:
        return self.connection

    async def __aexit__(self, *args: object) -> None:
        return None


class FakeAsyncSSH:
    class Error(Exception):
        pass

    class TimeoutError(Exception):
        pass

    def __init__(self) -> None:
        self.connection = FakeConnection()
        self.connects: list[dict[str, object]] = []
        self.imported_keys: list[bytes] = []

    def import_private_key(self, key_material: bytes) -> str:
        self.imported_keys.append(key_material)
        return "loaded-key"

    def connect(self, host: str, **kwargs: object) -> FakeConnectContext:
        self.connects.append({"host": host, "kwargs": kwargs})
        return FakeConnectContext(self.connection)


@pytest.mark.asyncio
async def test_asyncssh_executor_runs_remote_command_with_credentials(monkeypatch) -> None:
    fake_asyncssh = FakeAsyncSSH()
    monkeypatch.setattr("inflab.executor.asyncssh", fake_asyncssh)
    executor = AsyncSSHExecutor(
        SSHConnectionConfig(
            host="10.0.0.10",
            port=2222,
            username="seed",
            credential_type="password",
            secret="pw",
            known_hosts_policy="permissive",
            connect_timeout_seconds=9,
        )
    )

    result = await executor.run(
        CommandRecord(
            command="whoami",
            cwd="/tmp/work dir",
            env={"CUDA_VISIBLE_DEVICES": "0,1"},
            sudo=True,
        ),
        timeout_seconds=7,
    )

    assert result.exit_code == 0
    assert result.stdout == "remote-ok"
    assert fake_asyncssh.connects[0]["host"] == "10.0.0.10"
    assert fake_asyncssh.connects[0]["kwargs"] == {
        "port": 2222,
        "username": "seed",
        "connect_timeout": 9,
        "known_hosts": None,
        "password": "pw",
    }
    run = fake_asyncssh.connection.runs[0]
    assert run["timeout"] == 7
    assert "sudo -n -- sh -lc" in str(run["command"])
    assert "CUDA_VISIBLE_DEVICES=0,1" in str(run["command"])
    assert "whoami" in str(run["command"])


@pytest.mark.asyncio
async def test_asyncssh_executor_supports_private_key_and_sftp(monkeypatch) -> None:
    fake_asyncssh = FakeAsyncSSH()
    monkeypatch.setattr("inflab.executor.asyncssh", fake_asyncssh)
    executor = AsyncSSHExecutor(
        SSHConnectionConfig(
            host="host.example",
            username="seed",
            credential_type="private_key",
            secret="-----BEGIN OPENSSH PRIVATE KEY-----",
            known_hosts_policy="strict",
        )
    )

    upload = await executor.upload("/local/model", "/remote/model")
    download = await executor.download("/remote/log", "/local/log")

    assert upload.exit_code == 0
    assert download.exit_code == 0
    assert fake_asyncssh.imported_keys == [b"-----BEGIN OPENSSH PRIVATE KEY-----"]
    assert fake_asyncssh.connects[0]["kwargs"]["client_keys"] == ["loaded-key"]
    assert "known_hosts" not in fake_asyncssh.connects[0]["kwargs"]
    assert fake_asyncssh.connection.sftp.puts == [("/local/model", "/remote/model")]
    assert fake_asyncssh.connection.sftp.gets == [("/remote/log", "/local/log")]


@pytest.mark.asyncio
async def test_asyncssh_executor_reports_invalid_environment(monkeypatch) -> None:
    fake_asyncssh = FakeAsyncSSH()
    monkeypatch.setattr("inflab.executor.asyncssh", fake_asyncssh)
    executor = AsyncSSHExecutor(SSHConnectionConfig(host="host.example"))

    result = await executor.run(CommandRecord(command="echo nope", env={"BAD-NAME": "1"}))

    assert result.exit_code == 255
    assert "Invalid remote environment variable name" in result.stderr
    assert fake_asyncssh.connects == []


@pytest.mark.asyncio
async def test_asyncssh_executor_streams_process_lines(monkeypatch) -> None:
    fake_asyncssh = FakeAsyncSSH()
    monkeypatch.setattr("inflab.executor.asyncssh", fake_asyncssh)
    executor = AsyncSSHExecutor(SSHConnectionConfig(host="host.example"))
    lines: list[str] = []

    result = await executor.stream(CommandRecord(command="vllm bench serve"), on_line=lines.append)

    assert result.exit_code == 0
    assert result.stdout == "line-1\nline-2"
    assert result.stderr == "warn"
    assert lines == ["line-1", "line-2", "warn"]
    assert fake_asyncssh.connection.processes == [
        {"command": "vllm bench serve", "encoding": "utf-8"}
    ]
