from fastapi.testclient import TestClient
import pytest

from minio_bucket import app


@pytest.fixture
def client():
    return TestClient(app)
