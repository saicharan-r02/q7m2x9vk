import csv
import json
import math
import os
from collections import defaultdict
from datetime import datetime,time,timedelta,timezone
from pathlib import Path

DATA_DIR=Path(__file__).resolve().parents[1]/"data"
CUTOFF_UTC=time.fromisoformat(os.getenv("WIND_DECISION_CUTOFF_UTC","09:50"))

def parse_utc(value: str) -> datetime:
    parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
    if parsed.tzinfo is None:
        parsed=parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

def iso_utc(value: datetime) -> str:
    return value.isoformat().replace("+00:00","Z")

def load_json(filename: str) -> list[dict]:
    path=DATA_DIR/filename
    with path.open("r",encoding="utf-8") as file:
        records=json.load(file)
    if not isinstance(records, list):
        raise ValueError(f"{filename} must contain a JSON list")
    return records

def load_hourly_actuals(records: list[dict]) -> tuple[dict[datetime, float], int]:
    half_hourly={}
    for row in records:
        if row.get("startTime") is None:
            continue
        if row.get("generation") is None:
            continue
        start=parse_utc(row["startTime"])
        if start.minute not in (0,30):
            raise ValueError(f"Unexpected actual timestamp resolution: {iso_utc(start)}")

        if start in half_hourly:
            raise ValueError(f"Duplicate actual timestamp: {iso_utc(start)}")

        half_hourly[start]=float(row["generation"])

    grouped=defaultdict(dict)

    for start,generation in half_hourly.items():
        hour_start=start.replace(minute=0,second=0,microsecond=0)
        grouped[hour_start][start.minute]=generation

    hourly_actuals={}
    incomplete_hours=0

    for hour_start,slots in grouped.items():
        if 0 not in slots or 30 not in slots:
            incomplete_hours+=1
            continue

        hourly_actuals[hour_start]=(slots[0]+slots[30])/2

    return hourly_actuals, incomplete_hours

def main() -> None:
    actual_records=load_json("actual_wind.json")
    forecast_records=load_json("wind_forecasts.json")
    actual_by_hour,incomplete_actual_hours=load_hourly_actuals(actual_records)

    if not actual_by_hour:
        raise ValueError("No complete hourly actual intervals were found")

    forecasts_by_hour = defaultdict(dict)
    forecast_records_outside_window = 0
    duplicate_forecast_keys = 0

    for row in forecast_records:
        if (
            row.get("startTime") is None
            or row.get("publishTime") is None
            or row.get("generation") is None
        ):
            continue

        delivery_hour=parse_utc(row["startTime"])

        if delivery_hour not in actual_by_hour:
            forecast_records_outside_window += 1
            continue

        published = parse_utc(row["publishTime"])
        bucket = forecasts_by_hour[delivery_hour]

        if published in bucket:
            duplicate_forecast_keys += 1

        bucket[published] = float(row["generation"])

    matched = []
    missing_forecasts = 0

    for delivery_hour, actual_mw in sorted(actual_by_hour.items()):
        decision_date = delivery_hour.date() - timedelta(days=1)

        cutoff=datetime.combine(decision_date,CUTOFF_UTC,tzinfo=timezone.utc)

        eligible=[
            (published,generation)
            for published, generation
            in forecasts_by_hour.get(delivery_hour, {}).items()
            if published <= cutoff
        ]

        if not eligible:
            missing_forecasts += 1
            continue
        published,forecast_mw=max(eligible,key=lambda item: item[0])

        error_mw=forecast_mw-actual_mw

        matched.append({
            "delivery_start_utc": iso_utc(delivery_hour),
            "decision_date": decision_date.isoformat(),
            "cutoff_utc": iso_utc(cutoff),
            "forecast_publish_time_utc": iso_utc(published),
            "forecast_mw": forecast_mw,
            "actual_mw": actual_mw,
            "error_mw": error_mw,
            "absolute_error_mw": abs(error_mw)
        })

    actual_count=len(actual_by_hour)
    matched_count=len(matched)

    errors=[row["error_mw"] for row in matched]
    absolute_errors=[abs(error) for error in errors]
    actual_total=sum(row["actual_mw"] for row in matched)

    mae=(
        sum(absolute_errors)/matched_count
        if matched_count else None
    )
    rmse=(
        math.sqrt(sum(error**2 for error in errors)/matched_count)
        if matched_count else None
    )
    bias=(
        sum(errors)/matched_count
        if matched_count else None
    )
    wape=(
        sum(absolute_errors)/actual_total*100
        if matched_count and actual_total!=0 else None
    )

    summary={
        "analysis": (
            "January 2026 decision dates; next-day delivery assumption"
        ),
        "cutoff_utc": CUTOFF_UTC.isoformat(),
        "cutoff_note": (
            "Configurable demonstration assumption; "
            "not a client-confirmed market deadline."
        ),
        "actual_hourly_intervals": actual_count,
        "incomplete_actual_hours_excluded": incomplete_actual_hours,
        "matched_hourly_intervals": matched_count,
        "hours_without_eligible_forecast": missing_forecasts,
        "coverage_pct": round(
            matched_count / actual_count * 100, 2
        ) if actual_count else 0,
        "forecast_records_outside_actual_window": (
            forecast_records_outside_window
        ),
        "duplicate_forecast_interval_publication_keys": (
            duplicate_forecast_keys
        ),
        "mae_mw": round(mae, 2) if mae is not None else None,
        "rmse_mw": round(rmse, 2) if rmse is not None else None,
        "bias_mw": round(bias, 2) if bias is not None else None,
        "wape_pct": round(wape, 2) if wape is not None else None,
        "error_convention": (
            "forecast minus actual; positive means overforecast"
        )
    }

    csv_path = DATA_DIR / "evaluation.csv"
    fields = [
        "delivery_start_utc",
        "decision_date",
        "cutoff_utc",
        "forecast_publish_time_utc",
        "forecast_mw",
        "actual_mw",
        "error_mw",
        "absolute_error_mw"
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(matched)

    summary_path = DATA_DIR / "evaluation_summary.json"

    with summary_path.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    print("\nHOURLY FORECAST EVALUATION")
    for key, value in summary.items():
        print(f"{key}: {value}")

    print(f"\nSaved matched intervals: {csv_path}")
    print(f"Saved summary:           {summary_path}")

if __name__ == "__main__":
    main()