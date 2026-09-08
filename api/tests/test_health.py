from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app


class FakeSession:
    """Minimal stand-in so the test does not need a running Postgres."""

    async def execute(self, *args, **kwargs):
        return None

    async def close(self):
        return None


async def override_get_db():
    yield FakeSession()


client = TestClient(app)


def test_health_reports_ok_and_db_up():
    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["version"]
        assert body["checks"]["database"] == "up"
    finally:
        app.dependency_overrides.clear()
