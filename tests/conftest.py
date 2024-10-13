import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as _client:
        yield _client


@pytest.fixture
def other_client():
    with TestClient(app) as _client:
        yield _client
