
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def inspect_file(filename: str, required_fields: list[str]) -> None:
    path = DATA_DIR / filename

    with path.open("r", encoding="utf-8") as file:
        records = json.load(file)

    print(f"\n{'=' * 55}")
    print(f"File: {filename}")
    print(f"Records: {len(records):,}")

    if not records:
        print("ERROR: Dataset is empty.")
        return

    print("Fields:", ", ".join(records[0].keys()))

    for field in required_fields:
        missing = sum(
            record.get(field) is None
            for record in records
        )
        print(f"Missing {field}: {missing:,}")

    timestamps = [
        record["startTime"]
        for record in records
        if record.get("startTime")
    ]

    publications = [
        record["publishTime"]
        for record in records
        if record.get("publishTime")
    ]

    if timestamps:
        print(f"Delivery range: {min(timestamps)} to {max(timestamps)}")

    if publications:
        print(
            "Publication range:",
            f"{min(publications)} to {max(publications)}",
        )

    print("Sample record:", records[0])


def main() -> None:
    inspect_file(
        "actual_wind.json",
        ["startTime", "publishTime", "generation", "fuelType"],
    )

    inspect_file(
        "wind_forecasts.json",
        ["startTime", "publishTime", "generation"],
    )


if __name__ == "__main__":
    main()