from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from inflab.api.app import create_app
from inflab.config import AppSettings


@pytest.fixture
def settings() -> AppSettings:
    return AppSettings(environment="test", log_level="WARNING")


@pytest.fixture
def client(settings: AppSettings) -> Generator[TestClient, None, None]:
    with TestClient(create_app(settings=settings)) as test_client:
        yield test_client
