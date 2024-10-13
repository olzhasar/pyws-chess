from fastapi.testclient import TestClient


async def test_index(client: TestClient):
    response = client.get("/")

    assert response.status_code == 200


async def test_metrics(client: TestClient):
    response = client.get("/metrics")

    assert response.status_code == 200
