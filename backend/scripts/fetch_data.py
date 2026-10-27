import json
import time
from pathlib import Path
import requests

BASE_URL="https://data.elexon.co.uk/bmrs/api/v1/datasets"

ROOT=Path(__file__).resolve().parents[1]
DATA_DIR=ROOT/"data"
DATA_DIR.mkdir(parents=True,exist_ok=True)

SESSION=requests.Session()
SESSION.headers.update({"Accept": "application/json"})

def fetch_dataset(name: str,params: dict,output_name: str) -> None:
    url=f"{BASE_URL}/{name}/stream"

    for attempt in range(3):
        try:
            response=SESSION.get(
                url,
                params=params,
                timeout=120
            )

            if response.status_code==429:
                time.sleep(5*(attempt+1))
                continue
            response.raise_for_status()
            records=response.json()

            if not isinstance(records, list):
                raise ValueError(
                    f"Expected a JSON list from {name}, "
                    f"received {type(records).__name__}"
                )

            output_path=DATA_DIR/output_name

            with output_path.open("w",encoding="utf-8") as file:
                json.dump(records,file)

            print(f"\nDataset: {name}")
            print(f"Records: {len(records):,}")
            print(f"Saved:   {output_path}")

            if records:
                print("First record:")
                print(json.dumps(records[0],indent=2))

            return

        except (requests.RequestException, ValueError) as exc:
            print(f"Attempt {attempt+1} failed: {exc}")

            if attempt==2:
                raise

            time.sleep(2*(attempt+1))

    raise RuntimeError(f"Failed to fetch {name}")



def main() -> None:
    fetch_dataset(
        "FUELHH",
        {
            "settlementDateFrom": "2026-01-02",
            "settlementDateTo": "2026-02-01",
            "fuelType": "WIND"
        },
        "actual_wind.json"
    )

    fetch_dataset(
    "WINDFOR",
    {
        "publishDateTimeFrom": "2025-12-31T00:00:00Z",
        "publishDateTimeTo": "2026-01-31T23:59:59Z"
    },
    "wind_forecasts.json"
)

if __name__ == "__main__":
    main()