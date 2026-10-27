
import csv
import json
import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

app = FastAPI(
    title="Gridbricks Wind Intelligence API",
    description=(
        "Decision-time wind forecast evaluation using Elexon data."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def require_file(filename: str) -> Path:
    path = DATA_DIR / filename

    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"{filename} is missing. "
                "Run the data-fetching and evaluation scripts first."
            ),
        )

    return path


def read_json(filename: str) -> list | dict:
    path = require_file(filename)

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def read_evaluation() -> list[dict]:
    path = require_file("evaluation.csv")

    with path.open("r", newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))

    numeric_fields = [
        "forecast_mw",
        "actual_mw",
        "error_mw",
        "absolute_error_mw",
    ]

    for row in rows:
        for field in numeric_fields:
            row[field] = float(row[field])

    return rows


def calculate_metrics(rows: list[dict]) -> dict:
    if not rows:
        return {
            "sample_count": 0,
            "mae_mw": None,
            "rmse_mw": None,
            "bias_mw": None,
            "wape_pct": None,
        }

    errors = [row["error_mw"] for row in rows]
    absolute_errors = [abs(error) for error in errors]
    actual_total = sum(row["actual_mw"] for row in rows)

    return {
        "sample_count": len(rows),
        "mae_mw": round(
            sum(absolute_errors) / len(rows), 2
        ),
        "rmse_mw": round(
            math.sqrt(sum(error**2 for error in errors) / len(rows)),
            2,
        ),
        "bias_mw": round(sum(errors) / len(rows), 2),
        "wape_pct": (
            round(sum(absolute_errors) / actual_total * 100, 2)
            if actual_total != 0
            else None
        ),
    }


@app.get("/")
def root():
    return {
        "name": "Gridbricks Wind Intelligence API",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health")
def health():
    files = [
        "actual_wind.json",
        "wind_forecasts.json",
        "evaluation.csv",
        "evaluation_summary.json",
    ]

    status = {
        filename: (DATA_DIR / filename).exists()
        for filename in files
    }

    return {
        "status": "ok" if all(status.values()) else "not_ready",
        "files": status,
    }


@app.get("/api/summary")
def summary():
    data = read_json("evaluation_summary.json")

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=500,
            detail="Evaluation summary has an unexpected format.",
        )

    return data


@app.get("/api/evaluation")
def evaluation(
    decision_date: date | None = None,
    limit: int = Query(default=744, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    rows = read_evaluation()

    if decision_date:
        rows = [
            row for row in rows
            if row["decision_date"] == decision_date.isoformat()
        ]

    return {
        "total": len(rows),
        "limit": limit,
        "offset": offset,
        "items": rows[offset:offset + limit],
    }


@app.get("/api/daily-metrics")
def daily_metrics():
    rows = read_evaluation()
    grouped = defaultdict(list)

    for row in rows:
        grouped[row["decision_date"]].append(row)

    result = []

    for day in sorted(grouped):
        result.append({
            "decision_date": day,
            **calculate_metrics(grouped[day]),
        })

    return {"items": result}


@app.get("/api/forecast-evolution")
def forecast_evolution(
    delivery_start_utc: str = Query(
        description=(
            "Hourly delivery start, e.g. 2026-01-02T00:00:00Z"
        )
    ),
):
    try:
        target = parse_utc(delivery_start_utc)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail="Provide a valid ISO-8601 UTC timestamp.",
        )

    if target.minute != 0 or target.second != 0:
        raise HTTPException(
            status_code=400,
            detail="The delivery start must be on the hour.",
        )

    target_iso = target.isoformat().replace("+00:00", "Z")

    evaluation_rows = read_evaluation()
    selected = next(
        (
            row for row in evaluation_rows
            if parse_utc(row["delivery_start_utc"]) == target
        ),
        None,
    )

    if selected is None:
        raise HTTPException(
            status_code=404,
            detail="No evaluated delivery interval exists for that time.",
        )

    raw_forecasts = read_json("wind_forecasts.json")
    cutoff = parse_utc(selected["cutoff_utc"])
    selected_publish_time = parse_utc(
        selected["forecast_publish_time_utc"]
    )

    vintages = []

    for row in raw_forecasts:
        if (
            not row.get("startTime")
            or not row.get("publishTime")
            or row.get("generation") is None
        ):
            continue

        if parse_utc(row["startTime"]) != target:
            continue

        published = parse_utc(row["publishTime"])

        vintages.append({
            "publish_time_utc": (
                published.isoformat().replace("+00:00", "Z")
            ),
            "generation_mw": float(row["generation"]),
            "eligible_at_cutoff": published <= cutoff,
            "selected_for_decision": (
                published == selected_publish_time
            ),
        })

    vintages.sort(key=lambda item: item["publish_time_utc"])

    return {
        "delivery_start_utc": target_iso,
        "decision_date": selected["decision_date"],
        "cutoff_utc": selected["cutoff_utc"],
        "actual_mw": selected["actual_mw"],
        "selected_forecast_mw": selected["forecast_mw"],
        "selected_forecast_publish_time_utc": (
            selected["forecast_publish_time_utc"]
        ),
        "error_mw": selected["error_mw"],
        "vintages": vintages,
    }


@app.get("/api/analysis")
def analysis(
    month: str = Query(
        default="2026-01",
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
        description="Decision month in YYYY-MM format",
    ),
    cutoff_time: str = Query(
        default="09:50",
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
        description="Latest eligible forecast publication time, UK local time",
    ),
    refresh: bool = Query(default=False),
):
    """Build hourly decision-time metrics from the downloaded Elexon datasets.

    `month` refers to the decision month. Delivery is assumed to occur
    on the following calendar day. January is GMT, so UK time equals UTC.
    `refresh` is accepted for frontend compatibility; it does not download
    new data.
    """
    del refresh  # Local datasets are used; no live fetch is performed here.

    try:
        year, month_number = map(int, month.split("-"))
        month_start = date(year, month_number, 1)
        if month_number == 12:
            next_month_start = date(year + 1, 1, 1)
        else:
            next_month_start = date(year, month_number + 1, 1)
        cutoff_clock = time.fromisoformat(cutoff_time)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Provide a valid month (YYYY-MM) and cutoff time (HH:MM).",
        )

    actual_records = read_json("actual_wind.json")
    forecast_records = read_json("wind_forecasts.json")

    if not isinstance(actual_records, list) or not isinstance(
        forecast_records, list
    ):
        raise HTTPException(
            status_code=500,
            detail="The downloaded Elexon datasets must contain JSON lists.",
        )

    # Deduplicate actual observations by delivery timestamp, keeping
    # the record with the latest publication time.
    half_hour_actuals: dict[datetime, tuple[datetime, float]] = {}

    for record in actual_records:
        if not record.get("startTime") or record.get("generation") is None:
            continue

        try:
            delivery_start = parse_utc(record["startTime"])
            publication_value = (
                record.get("publishTime")
                or record.get("publishDateTime")
                or record["startTime"]
            )
            published = parse_utc(publication_value)
            generation = float(record["generation"])
        except (ValueError, TypeError, KeyError):
            continue

        if delivery_start.minute not in (0, 30):
            continue

        previous = half_hour_actuals.get(delivery_start)
        if previous is None or published >= previous[0]:
            half_hour_actuals[delivery_start] = (published, generation)

    # Aggregate two half-hourly actual observations to an hourly mean.
    slots_by_hour: dict[datetime, dict[int, float]] = defaultdict(dict)

    for start, (_, generation) in half_hour_actuals.items():
        hour_start = start.replace(
            minute=0, second=0, microsecond=0
        )
        slots_by_hour[hour_start][start.minute] = generation

    hourly_actuals: dict[datetime, float] = {}
    incomplete_actual_hours = 0

    for hour_start, slots in slots_by_hour.items():
        decision_date = hour_start.date() - timedelta(days=1)

        if not (month_start <= decision_date < next_month_start):
            continue

        if 0 not in slots or 30 not in slots:
            incomplete_actual_hours += 1
            continue

        hourly_actuals[hour_start] = (
            slots[0] + slots[30]
        ) / 2

    # Index forecast vintages by delivery hour and publication timestamp.
    forecasts_by_hour: dict[datetime, dict[datetime, float]] = defaultdict(dict)

    for record in forecast_records:
        if (
            not record.get("startTime")
            or not record.get("publishTime")
            or record.get("generation") is None
        ):
            continue

        try:
            delivery_start = parse_utc(record["startTime"])
            published = parse_utc(record["publishTime"])
            generation = float(record["generation"])
        except (ValueError, TypeError, KeyError):
            continue

        # WINDFOR forecasts in this analysis are hourly.
        if delivery_start.minute != 0:
            continue

        forecasts_by_hour[delivery_start][published] = generation

    periods: list[dict] = []
    selected_publications: list[datetime] = []

    for delivery_start, actual_mw in sorted(hourly_actuals.items()):
        decision_date = delivery_start.date() - timedelta(days=1)
        cutoff = datetime.combine(
            decision_date,
            cutoff_clock,
            tzinfo=timezone.utc,
        )

        eligible = [
            (published, generation)
            for published, generation
            in forecasts_by_hour.get(delivery_start, {}).items()
            if published <= cutoff
        ]

        selected_publish: datetime | None = None
        forecast_mw: float | None = None

        if eligible:
            selected_publish, forecast_mw = max(
                eligible,
                key=lambda item: item[0],
            )
            selected_publications.append(selected_publish)

        error_mw = (
            forecast_mw - actual_mw
            if forecast_mw is not None
            else None
        )

        periods.append({
            "start_time": (
                delivery_start.isoformat().replace("+00:00", "Z")
            ),
            "decision_date": decision_date.isoformat(),
            "decision_cutoff": cutoff.isoformat().replace("+00:00", "Z"),
            "delivery_date": delivery_start.date().isoformat(),
            # Compatibility field: this is an hourly index (1–24),
            # not an Elexon half-hourly settlement-period number.
            "settlement_period": delivery_start.hour + 1,
            "period_label": (
                f"{delivery_start:%H:%M}–"
                f"{(delivery_start.hour + 1) % 24:02d}:00"
            ),
            "actual_mw": round(actual_mw, 3),
            "forecast_mw": (
                round(forecast_mw, 3)
                if forecast_mw is not None else None
            ),
            "error_mw": (
                round(error_mw, 3)
                if error_mw is not None else None
            ),
            "abs_error_mw": (
                round(abs(error_mw), 3)
                if error_mw is not None else None
            ),
            "forecast_publish_time": (
                selected_publish.isoformat().replace("+00:00", "Z")
                if selected_publish is not None else None
            ),
            "lead_time_hours": (
                round(
                    (delivery_start - selected_publish).total_seconds()
                    / 3600,
                    2,
                )
                if selected_publish is not None else None
            ),
        })

    if not periods:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No complete hourly actual observations found for "
                f"decision month {month}."
            ),
        )

    matched = [
        row for row in periods
        if row["forecast_mw"] is not None and row["error_mw"] is not None
    ]
    metrics = calculate_metrics(matched)

    daily_groups: dict[str, list[dict]] = defaultdict(list)
    for row in periods:
        daily_groups[row["delivery_date"]].append(row)

    daily: list[dict] = []

    for delivery_date in sorted(daily_groups):
        day_rows = daily_groups[delivery_date]
        day_matched = [
            row for row in day_rows
            if row["forecast_mw"] is not None
            and row["error_mw"] is not None
        ]

        def mean_of(values: list[float]) -> float | None:
            return (
                round(sum(values) / len(values), 3)
                if values else None
            )

        day_metrics = calculate_metrics(day_matched)

        daily.append({
            "decision_date": day_rows[0]["decision_date"],
            "delivery_date": delivery_date,
            "actual_mean_mw": mean_of([
                row["actual_mw"] for row in day_rows
                if row["actual_mw"] is not None
            ]),
            "forecast_mean_mw": mean_of([
                row["forecast_mw"] for row in day_rows
                if row["forecast_mw"] is not None
            ]),
            "matched_periods": len(day_matched),
            "actual_periods": sum(
                row["actual_mw"] is not None for row in day_rows
            ),
            "forecast_periods": sum(
                row["forecast_mw"] is not None for row in day_rows
            ),
            "mae_mw": day_metrics["mae_mw"],
            "bias_mw": day_metrics["bias_mw"],
        })

    return {
        "meta": {
            "decision_month": month,
            "timezone": "Europe/London",
            "cutoff_time": cutoff_time,
            "decision_days": len({
                row["decision_date"] for row in periods
            }),
            "delivery_start": min(
                row["delivery_date"] for row in periods
            ),
            "delivery_end": max(
                row["delivery_date"] for row in periods
            ),
            "units": "MW",
            "actual_dataset": "FUELHH",
            "forecast_dataset": "WINDFOR",
            "method": (
                "Hourly WINDFOR forecast compared with the mean of "
                "the two corresponding half-hourly FUELHH actuals. "
                "For each delivery hour, choose the latest forecast "
                "published on or before the previous-day cutoff."
            ),
        },
        "summary": {
            "matched_periods": metrics["sample_count"],
            "mae_mw": metrics["mae_mw"],
            "rmse_mw": metrics["rmse_mw"],
            "bias_mw": metrics["bias_mw"],
            "wape_pct": metrics["wape_pct"],
            "expected_periods": len(periods),
            "actual_periods": sum(
                row["actual_mw"] is not None for row in periods
            ),
            "forecast_periods": sum(
                row["forecast_mw"] is not None for row in periods
            ),
            "actual_forecast_pairs": metrics["sample_count"],
            "coverage_pct": round(
                metrics["sample_count"] / len(periods) * 100, 2
            ) if periods else 0,
            "latest_selected_publish_time": (
                max(selected_publications).isoformat().replace("+00:00", "Z")
                if selected_publications else None
            ),
        },
        "daily": daily,
        "periods": periods,
    }
