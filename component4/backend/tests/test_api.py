from io import BytesIO

import pytest

from app import create_app, db
from app.models import QualityAlert


@pytest.fixture()
def client():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
    })
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_health_summary_and_validation(client):
    assert client.get("/api/v1/health").get_json()["data"]["database"] == "ok"
    invalid = client.post("/api/v1/production", json={
        "batch_id": "B-1", "production_timestamp": "2026-01-01T00:00:00Z",
        "production_quantity": 10, "inspected_quantity": 11,
    })
    assert invalid.status_code == 400
    assert client.get("/api/v1/dashboard/summary").get_json()["data"]["batch_count"] == 0


def test_production_create_filter_and_pagination(client):
    created = client.post("/api/v1/production", json={
        "batch_id": "B-1", "production_timestamp": "2026-01-01T00:00:00Z",
        "production_quantity": 10, "inspected_quantity": 10,
        "accepted_quantity": 9, "rejected_quantity": 1,
    })
    assert created.status_code == 201
    listing = client.get("/api/v1/production?batch_id=B-1&page=1&per_page=1")
    assert listing.status_code == 200
    assert listing.get_json()["meta"]["total"] == 1
    assert client.get("/api/v1/batches/B-1").status_code == 200


def test_csv_preview_and_transactional_import(client):
    csv_data = b"batch_id,production_timestamp,production_quantity\nCSV-1,2026-01-01T00:00:00Z,25\n"
    preview = client.post("/api/v1/data-management/import", data={
        "file": (BytesIO(csv_data), "production.csv"), "preview": "true",
    }, content_type="multipart/form-data")
    assert preview.status_code == 200
    imported = client.post("/api/v1/data-management/import", data={
        "file": (BytesIO(csv_data), "production.csv"),
    }, content_type="multipart/form-data")
    assert imported.status_code == 201
    assert client.get("/api/v1/data-management/summary").get_json()["data"]["production_records"] == 1


def test_predictive_api_reports_untrained_and_insufficient_states(client, tmp_path):
    client.application.config["PREDICTIVE_MODEL_DIR"] = str(tmp_path)
    status = client.get("/api/v1/predictions/status")
    assert status.status_code == 200
    assert status.get_json()["data"]["state"] == "untrained"
    training = client.post("/api/v1/predictions/train")
    assert training.status_code == 422
    assert training.get_json()["data"]["state"] == "insufficient_data"


def test_alert_filters_and_status_update(client):
    with client.application.app_context():
        db.session.add(QualityAlert(
            severity="high", title="Reject rate high", description="Measured",
            batch_id=None, triggering_metric="rejection_rate", observed_value=8,
            threshold_or_risk_context="5", recommendation="Review batch", status="Open",
        ))
        db.session.commit()
    filtered = client.get("/api/v1/alerts?severity=high&status=Open")
    assert filtered.status_code == 200
    alert_id = filtered.get_json()["data"][0]["id"]
    updated = client.patch(f"/api/v1/alerts/{alert_id}", json={"status": "Acknowledged"})
    assert updated.get_json()["data"]["status"] == "Acknowledged"
    assert client.get("/api/v1/alerts/summary").get_json()["data"]["active_total"] == 1


def test_report_preview_and_exports(client):
    preview = client.post("/api/v1/reports/preview", json={"report_type": "daily-production"})
    assert preview.status_code == 200
    csv_export = client.post("/api/v1/reports/export", json={
        "report_type": "daily-production", "format": "csv",
    })
    assert csv_export.status_code == 200
    assert csv_export.mimetype == "text/csv"
    pdf_export = client.post("/api/v1/reports/export", json={
        "report_type": "daily-production", "format": "pdf",
    })
    assert pdf_export.status_code == 200
    assert pdf_export.data.startswith(b"%PDF")
