"""Tests for GET /api/health."""


def test_health_returns_200(client):
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.json() == {"status": "ok"}
