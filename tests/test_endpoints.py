import os
import secrets
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
os.environ.setdefault("JWT_SECRET_KEY", secrets.token_urlsafe(48))
os.environ.setdefault("INITIAL_ADMIN_PASSWORD", secrets.token_urlsafe(24))
from backend.main import app
from backend.init_db import populate_database

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_test_db():
    populate_database()

def test_root_endpoint():
    res = client.get("/")
    assert res.status_code == 200
    assert "message" in res.json()

def test_sync_status():
    res = client.get("/api/dashboard/sync-status")
    assert res.status_code == 200
    data = res.json()
    assert "last_updated" in data
    assert "status" in data

def test_notifications():
    res = client.get("/api/notifications")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    if len(data) > 0:
        alert = data[0]
        assert "severity" in alert
        assert "message" in alert

def test_routes_list():
    res = client.get("/api/routes/list")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert "route_id" in data[0]
    assert "route_name" in data[0]

def test_dashboard_summary():
    res = client.get("/api/dashboard/summary")
    assert res.status_code == 200
    data = res.json()
    assert "total_passengers" in data
    assert "total_passengers_change_pct" in data
    assert "total_trips" in data
    assert "total_trips_change_pct" in data
    assert "avg_occupancy_pct" in data
    assert "avg_occupancy_change_pct" in data
    assert "on_time_pct" in data
    assert "on_time_change_pct" in data

def test_top_routes():
    res = client.get("/api/dashboard/top-routes?limit=5")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) <= 5
    if len(data) > 0:
        assert "route_id" in data[0]
        assert "total_passengers" in data[0]

def test_delays_by_cause():
    res = client.get("/api/delays/by-cause")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "cause" in data[0]
        assert "incident_count" in data[0]
        assert "percentage_share" in data[0]

def test_map_routes_geo():
    res = client.get("/api/map/routes-geo")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "route_id" in data[0]
        assert "status_color" in data[0]
        assert "path" in data[0]

def test_map_delay_hotspots():
    res = client.get("/api/map/delay-hotspots")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "stop_id" in data[0]
        assert "delay_events" in data[0]

def test_route_by_id():
    routes_res = client.get("/api/routes/list")
    first_id = routes_res.json()[0]["route_id"]

    res = client.get(f"/api/routes/{first_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["route_id"] == first_id
    assert "avg_delay_minutes" in data
    assert "occupancy_pct" in data
    assert "on_time_pct" in data
    assert "performance_category" in data

def test_whatif_simulation():
    unauthorized = client.post("/api/whatif/simulate", json={
        "route_id": "ROUTE_001",
        "change_type": "frequency",
        "change_value": 20.0,
    })
    assert unauthorized.status_code == 401

    login = client.post("/api/auth/login", json={
        "username": "admin",
        "password": os.environ["INITIAL_ADMIN_PASSWORD"],
    })
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    routes = client.get("/api/routes/list").json()
    assert routes
    payload = {
        "route_id": routes[0]["route_id"],
        "change_type": "frequency",
        "change_value": 20.0
    }
    res = client.post("/api/whatif/simulate", json=payload, headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "before" in data
    assert "after" in data
    assert data["is_estimate"] == True
    assert "occupancy_pct" in data["before"]
    assert "avg_wait_min" in data["before"]

    missing = client.post("/api/whatif/simulate", json={
        **payload,
        "route_id": "UNKNOWN_ROUTE",
    }, headers=headers)
    assert missing.status_code == 404

def test_occupancy_hourly():
    res = client.get("/api/occupancy/hourly")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

def test_forecast_demand():
    res = client.get("/api/forecast/demand")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

def test_recommendations():
    res = client.get("/api/recommendations")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

def test_model_comparison():
    res = client.get("/api/models/comparison")
    assert res.status_code == 200
    assert "models" in res.json()
