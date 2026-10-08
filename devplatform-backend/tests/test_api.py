import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_api_key_enforced(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "api_key", "secret")
    assert client.get("/api/repositories").status_code == 401
    assert client.get("/api/repositories", headers={"X-API-Key": "wrong"}).status_code == 401


def test_invalid_repo_url_rejected(client):
    r = client.post("/api/repositories", json={"url": "https://example.com/not-github"})
    assert r.status_code == 422
