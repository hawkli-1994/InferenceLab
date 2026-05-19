from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from inflab.api.app import create_app
from inflab.config import AppSettings, DatabaseSettings


@pytest.fixture
def settings() -> AppSettings:
    return AppSettings(
        environment="test",
        log_level="WARNING",
        database=DatabaseSettings(
            url="sqlite+pysqlite:///:memory:",
            create_schema_on_startup=True,
        ),
    )


@pytest.fixture
def client(settings: AppSettings) -> Generator[TestClient, None, None]:
    with TestClient(create_app(settings=settings)) as test_client:
        yield test_client
