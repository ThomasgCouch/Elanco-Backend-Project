"""Load cleaned sightings into a SQLite database."""

import json
import os
import sqlite3

from ingest.regions import region_for

CLEAN_PATH = os.path.join("data", "clean_sightings.json")
DB_PATH = os.path.join("data", "sightings.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS sightings (
    id          TEXT PRIMARY KEY,
    date        TEXT NOT NULL,      -- ISO 8601, e.g. 2025-08-14T17:30:00
    location    TEXT NOT NULL,
    region      TEXT NOT NULL,
    species     TEXT NOT NULL,
    latin_name  TEXT
);
CREATE INDEX IF NOT EXISTS idx_sightings_date     ON sightings (date);
CREATE INDEX IF NOT EXISTS idx_sightings_location ON sightings (location);
CREATE INDEX IF NOT EXISTS idx_sightings_region   ON sightings (region);
CREATE INDEX IF NOT EXISTS idx_sightings_species  ON sightings (species);
"""


def get_connection(path=DB_PATH):
    """Open a connection that returns rows as dict-like objects."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def load(sightings, conn):
    """Insert or update sightings. Safe to re-run: same id = same row."""
    conn.executescript(SCHEMA)
    rows = [
        (
            s["id"],
            s["date"],
            s["location"],
            region_for(s["location"]),
            s["species"],
            s.get("latinName"),
        )
        for s in sightings
    ]
    with conn:  # commits on success, rolls back on error
        conn.executemany(
            """
            INSERT INTO sightings (id, date, location, region, species, latin_name)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                date = excluded.date,
                location = excluded.location,
                region = excluded.region,
                species = excluded.species,
                latin_name = excluded.latin_name
            """,
            rows,
        )
    return len(rows)


def main():
    with open(CLEAN_PATH, encoding="utf-8") as f:
        sightings = json.load(f)

    conn = get_connection()
    count = load(sightings, conn)
    total = conn.execute("SELECT COUNT(*) FROM sightings").fetchone()[0]
    conn.close()

    print(f"Loaded {count} sightings; database now holds {total} rows ({DB_PATH})")


if __name__ == "__main__":
    main()