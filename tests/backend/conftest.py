import pytest
from fastapi.testclient import TestClient
from lifeos.main import create_app
from lifeos.config import Settings


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(Settings(database_url=f"sqlite:///{tmp_path}/test.db"))) as c:
        session = c.get("/api/session").json()
        c.headers["X-CSRF-Token"] = session["csrf_token"]
        yield c
