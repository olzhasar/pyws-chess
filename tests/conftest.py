import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
async def app():
    return create_app()


@pytest.fixture
async def client(app: FastAPI):
    with TestClient(app) as _client:
        yield _client


@pytest.fixture
async def other_client(app: FastAPI):
    with TestClient(app) as _client:
        yield _client
