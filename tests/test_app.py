from fastapi.testclient import TestClient


async def test_index(client: TestClient):
    response = client.get("/")

    assert response.status_code == 200
