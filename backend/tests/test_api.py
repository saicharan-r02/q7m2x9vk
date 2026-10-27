
import json

import pytest
from fastapi.testclient import TestClient

import app as api


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Use isolated sample data instead of modifying real project data."""
    monkeypatch.setattr(api, "DATA_DIR", tmp_path)

    actuals = [
        {
            "startTime": "2026-01-02T00:00:00Z",
            "publishTime": "2026-01-02T00:30:00Z",
            "generation": 100,
        },
        {
            "startTime": "2026-01-02T00:30:00Z",
            "publishTime": "2026-01-02T01:00:00Z",
            "generation": 120,
        },
        {
            "startTime": "2026-01-02T01:00:00Z",
            "publishTime": "2026-01-02T01:30:00Z",
            "generation": 140,
        },
        {
            "startTime": "2026-01-02T01:30:00Z",
            "publishTime": "2026-01-02T02:00:00Z",
            "generation": 160,
        },
        {
            "startTime": "2026-01-02T02:00:00Z",
            "publishTime": "2026-01-02T02:30:00Z",
            "generation": 180,
        },
        {
            "startTime": "2026-01-02T02:30:00Z",
            "publishTime": "2026-01-02T03:00:00Z",
            "generation": 200,
        },
    ]

    forecasts = [
        # Delivery hour 00:00: these vintages become eligible in order.
        {
            "startTime": "2026-01-02T00:00:00Z",
            "publishTime": "2026-01-01T08:30:00Z",
            "generation": 90,
        },
        {
            "startTime": "2026-01-02T00:00:00Z",
            "publishTime": "2026-01-01T09:30:00Z",
            "generation": 105,
        },
        {
            "startTime": "2026-01-02T00:00:00Z",
            "publishTime": "2026-01-01T10:30:00Z",
            "generation": 95,
        },

        # Delivery hour 01:00.
        {
            "startTime": "2026-01-02T01:00:00Z",
            "publishTime": "2026-01-01T08:30:00Z",
            "generation": 145,
        },
        {
            "startTime": "2026-01-02T01:00:00Z",
            "publishTime": "2026-01-01T09:30:00Z",
            "generation": 155,
        },

        # Delivery hour 02:00 has no forecast before 09:30.
        {
            "startTime": "2026-01-02T02:00:00Z",
            "publishTime": "2026-01-01T10:30:00Z",
            "generation": 190,
        },
    ]

    (tmp_path / "actual_wind.json").write_text(
        json.dumps(actuals), encoding="utf-8"
    )
    (tmp_path / "wind_forecasts.json").write_text(
        json.dumps(forecasts), encoding="utf-8"
    )

    return TestClient(api.app)


def test_analysis_metrics_and_missing_forecast(client):
    response = client.get(
        "/api/analysis",
        params={"month": "2026-01", "cutoff_time": "09:30"},
    )

    assert response.status_code == 200
    result = response.json()

    assert result["summary"]["expected_periods"] == 3
    assert result["summary"]["matched_periods"] == 2
    assert result["summary"]["coverage_pct"] == pytest.approx(66.67)

    # Actual hourly means: 110, 150.
    # Selected forecasts at 09:30: 105, 155.
    assert result["summary"]["mae_mw"] == pytest.approx(5.0)
    assert result["summary"]["rmse_mw"] == pytest.approx(5.0)
    assert result["summary"]["bias_mw"] == pytest.approx(0.0)

    unmatched = result["periods"][2]
    assert unmatched["actual_mw"] == pytest.approx(190.0)
    assert unmatched["forecast_mw"] is None
    assert unmatched["error_mw"] is None


def test_cutoff_selects_latest_eligible_vintage(client):
    earlier = client.get(
        "/api/analysis",
        params={"month": "2026-01", "cutoff_time": "09:00"},
    ).json()

    later = client.get(
        "/api/analysis",
        params={"month": "2026-01", "cutoff_time": "09:30"},
    ).json()

    assert earlier["periods"][0]["forecast_mw"] == pytest.approx(90.0)
    assert later["periods"][0]["forecast_mw"] == pytest.approx(105.0)

    assert (
        later["periods"][0]["forecast_publish_time"]
        == "2026-01-01T09:30:00Z"
    )


def test_forecast_published_after_cutoff_is_excluded(client):
    result = client.get(
        "/api/analysis",
        params={"month": "2026-01", "cutoff_time": "09:00"},
    ).json()

    # The 09:30 and 10:30 vintages are not eligible at 09:00.
    assert result["periods"][0]["forecast_mw"] == pytest.approx(90.0)
    assert result["periods"][2]["forecast_mw"] is None


def test_invalid_cutoff_is_rejected(client):
    response = client.get(
        "/api/analysis",
        params={"month": "2026-01", "cutoff_time": "25:90"},
    )

    assert response.status_code == 422


def test_invalid_month_is_rejected(client):
    response = client.get(
        "/api/analysis",
        params={"month": "2026-13", "cutoff_time": "09:30"},
    )

    assert response.status_code == 422
