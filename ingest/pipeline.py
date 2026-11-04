"""Run the full data pipeline: fetch -> clean -> load."""

from ingest.clean import clean
from ingest.fetch import fetch_sightings, save_raw
from ingest.load import get_connection, load


def main():
    print("1/3 Fetching from API...")
    raw = fetch_sightings()
    save_raw(raw)

    print("2/3 Cleaning...")
    cleaned, report = clean(raw)
    for key, value in report.items():
        print(f"    {key}: {value}")

    print("3/3 Loading into database...")
    conn = get_connection()
    count = load(cleaned, conn)
    conn.close()

    print(f"Done: {count} sightings ready.")


if __name__ == "__main__":
    main()