
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def parse_time(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def load(name):
    with (DATA_DIR / name).open(encoding="utf-8") as file:
        return json.load(file)


actuals = load("actual_wind.json")
forecasts = load("wind_forecasts.json")

actual_times = {
    parse_time(row["startTime"])
    for row in actuals
    if row.get("startTime")
}

forecast_times = {
    parse_time(row["startTime"])
    for row in forecasts
    if row.get("startTime")
}

actual_minutes = Counter(t.minute for t in actual_times)
forecast_minutes = Counter(
    parse_time(row["startTime"]).minute
    for row in forecasts
    if row.get("startTime")
)

exact_matches = actual_times & forecast_times

hourly_pairs = [
    t for t in exact_matches
    if t.minute == 0 and t + timedelta(minutes=30) in actual_times
]

print("ACTUAL timestamp minute distribution:", dict(actual_minutes))
print("FORECAST record minute distribution:", dict(forecast_minutes))
print("Unique actual timestamps:", len(actual_times))
print("Unique forecast target timestamps:", len(forecast_times))
print("Exact timestamp matches:", len(exact_matches))
print("Hourly starts with both half-hour actuals:", len(hourly_pairs))

print("\nFirst 8 actual timestamps:")
for t in sorted(actual_times)[:8]:
    print(t.isoformat())

print("\nFirst 8 forecast target timestamps:")
for t in sorted(forecast_times)[:8]:
    print(t.isoformat())

print("\nExample hourly matches:")
for t in sorted(hourly_pairs)[:5]:
    print(
        f"Forecast target: {t.isoformat()} | "
        f"actual intervals: {t.isoformat()} and "
        f"{(t + timedelta(minutes=30)).isoformat()}"
    )