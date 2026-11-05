"""API tests using a temporary database with known data."""

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_db
from ingest.load import get_connection, load

SAMPLE = [
    {"id": "s1", "date": "2025-06-01T10:00:00", "location": "London", "species": "Marsh tick", "latinName": "X"},
    {"id": "s2", "date": "2025-06-20T10:00:00", "location": "Manchester", "species": "Marsh tick", "latinName": "X"},
    {"id": "s3", "date": "2025-07-05T10:00:00", "location": "Liverpool", "species": "Passerine tick", "latinName": "Y"},
    {"id": "s4", "date": "2025-08-10T10:00:00", "location": "Glasgow", "species": "Tree-hole tick", "latinName": "Z"},
]


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(db_path)
    load(SAMPLE, conn)
    conn.close()

    def override_get_db():
        conn = get_connection(db_path)
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_returns_all(client):
    body = client.get("/sightings").json()
    assert body["total"] == 4


def test_filter_by_location_is_case_insensitive(client):
    body = client.get("/sightings", params={"location": "london"}).json()
    assert body["total"] == 1
    assert body["results"][0]["id"] == "s1"


def test_filter_by_date_range_is_inclusive(client):
    body = client.get("/sightings", params={"start": "2025-06-01", "end": "2025-06-20"}).json()
    assert {r["id"] for r in body["results"]} == {"s1", "s2"}


def test_invalid_date_range_returns_400(client):
    response = client.get("/sightings", params={"start": "2025-09-01", "end": "2025-01-01"})
    assert response.status_code == 400


def test_bad_date_format_returns_422(client):
    response = client.get("/sightings", params={"start": "not-a-date"})
    assert response.status_code == 422


def test_unknown_id_returns_404(client):
    assert client.get("/sightings/nope").status_code == 404


def test_counts_by_region(client):
    body = client.get("/stats/counts", params={"group_by": "region"}).json()
    counts = {r["name"]: r["sightings"] for r in body["results"]}
    assert counts["North West"] == 2   # Manchester + Liverpool
    assert counts["London"] == 1


def test_monthly_trends(client):
    body = client.get("/stats/trends", params={"interval": "month"}).json()
    counts = {r["period"]: r["sightings"] for r in body["results"]}
    assert counts == {"2025-06": 2, "2025-07": 1, "2025-08": 1}