import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
async def client():
    with TestClient(app) as _client:
        yield _client


@pytest.fixture
async def other_client():
    with TestClient(app) as _client:
        yield _client
