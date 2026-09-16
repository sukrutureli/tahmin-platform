import argparse
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from .scraper import fetch_basketball_matches, fetch_football_matches


def write_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="YYYY-MM-DD", default=None)
    args = parser.parse_args()

    date_str = args.date or datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%Y-%m-%d")

    print(f"📅 Fetching matches for {date_str}")

    football_matches = fetch_football_matches(date_str)
    basketball_matches = fetch_basketball_matches(date_str)

    os.makedirs("output", exist_ok=True)

    football_dated_path = f"output/{date_str}.json"
    football_latest_path = "output/latest.json"

    basketball_dated_path = f"output/basketbol-{date_str}.json"
    basketball_latest_path = "output/latestBasketbol.json"

    write_json(football_dated_path, football_matches)
    write_json(football_latest_path, football_matches)
    write_json(basketball_dated_path, basketball_matches)
    write_json(basketball_latest_path, basketball_matches)

    print(f"✅ Saved {len(football_matches)} football matches")
    print(f"📁 {football_dated_path}")
    print(f"📁 {football_latest_path}")

    print(f"✅ Saved {len(basketball_matches)} basketball matches")
    print(f"📁 {basketball_dated_path}")
    print(f"📁 {basketball_latest_path}")


if __name__ == "__main__":
    main()
