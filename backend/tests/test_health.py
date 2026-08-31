def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_ready(client):
    response = client.get("/ready")
    assert response.status_code == 200