"""Tick Sightings API: search, filter and report on cleaned UK tick sighting data."""

import os
from datetime import date, timedelta
from enum import Enum

from fastapi import Depends, FastAPI, HTTPException, Query

from ingest.load import DB_PATH, get_connection

app = FastAPI(
    title="UK Tick Sightings API",
    description="Search, filter and analyse UK tick sightings sourced from the Elanco Tick Sightings API.",
    version="1.0.0",
)


def get_db():
    """Give each request its own database connection, and close it afterwards."""
    if not os.path.exists(DB_PATH):
        raise HTTPException(
            status_code=503,
            detail="Database not found. Run `python -m ingest.pipeline` first.",
        )
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def build_filters(start, end, location, region, species):
    """Turn optional query parameters into a SQL WHERE clause and its values."""
    if start and end and start > end:
        raise HTTPException(status_code=400, detail="'start' must be on or before 'end'.")

    clauses, params = [], []
    if start:
        clauses.append("date >= ?")
        params.append(start.isoformat())
    if end:
        clauses.append("date < ?")  # end date is inclusive, so compare to the next day
        params.append((end + timedelta(days=1)).isoformat())
    if location:
        clauses.append("location = ? COLLATE NOCASE")  # 'london' matches 'London'
        params.append(location.strip())
    if region:
        clauses.append("region = ? COLLATE NOCASE")
        params.append(region.strip())
    if species:
        clauses.append("species = ? COLLATE NOCASE")
        params.append(species.strip())

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


@app.get("/", tags=["General"])
def root():
    return {"message": "UK Tick Sightings API. See /docs for interactive documentation."}


@app.get("/health", tags=["General"])
def health(conn=Depends(get_db)):
    count = conn.execute("SELECT COUNT(*) FROM sightings").fetchone()[0]
    return {"status": "ok", "sightings": count}


@app.get("/sightings", tags=["Sightings"])
def list_sightings(
    start: date | None = Query(None, description="Earliest date (YYYY-MM-DD), inclusive"),
    end: date | None = Query(None, description="Latest date (YYYY-MM-DD), inclusive"),
    location: str | None = Query(None, description="City, case-insensitive, e.g. london"),
    region: str | None = Query(None, description="UK region, e.g. North West"),
    species: str | None = Query(None, description="Species name, case-insensitive"),
    limit: int = Query(50, ge=1, le=500, description="Results per page"),
    offset: int = Query(0, ge=0, description="Results to skip"),
    conn=Depends(get_db),
):
    """Search sightings by time range, location and species, with pagination."""
    where, params = build_filters(start, end, location, region, species)

    total = conn.execute(f"SELECT COUNT(*) FROM sightings {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM sightings {where} ORDER BY date DESC LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": [dict(r) for r in rows],
    }


@app.get("/sightings/{sighting_id}", tags=["Sightings"])
def get_sighting(sighting_id: str, conn=Depends(get_db)):
    row = conn.execute("SELECT * FROM sightings WHERE id = ?", [sighting_id]).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Sighting '{sighting_id}' not found.")
    return dict(row)


class GroupBy(str, Enum):
    location = "location"
    region = "region"
    species = "species"


@app.get("/stats/counts", tags=["Reports"])
def counts(
    group_by: GroupBy = Query(GroupBy.region, description="What to count sightings by"),
    start: date | None = None,
    end: date | None = None,
    species: str | None = None,
    conn=Depends(get_db),
):
    """Number of sightings per region, location or species (optionally filtered)."""
    where, params = build_filters(start, end, None, None, species)
    column = group_by.value  # safe: restricted to the enum values above
    rows = conn.execute(
        f"SELECT {column} AS name, COUNT(*) AS sightings FROM sightings {where} "
        f"GROUP BY {column} ORDER BY sightings DESC",
        params,
    ).fetchall()
    return {"group_by": column, "results": [dict(r) for r in rows]}


class Interval(str, Enum):
    week = "week"
    month = "month"


@app.get("/stats/trends", tags=["Reports"])
def trends(
    interval: Interval = Query(Interval.month, description="Group by week or month"),
    start: date | None = None,
    end: date | None = None,
    location: str | None = None,
    region: str | None = None,
    species: str | None = None,
    conn=Depends(get_db),
):
    """Sightings over time, grouped by week or month (optionally filtered)."""
    where, params = build_filters(start, end, location, region, species)
    period = "strftime('%Y-%m', date)" if interval == Interval.month else "strftime('%Y-W%W', date)"
    rows = conn.execute(
        f"SELECT {period} AS period, COUNT(*) AS sightings FROM sightings {where} "
        f"GROUP BY period ORDER BY period",
        params,
    ).fetchall()
    return {"interval": interval.value, "results": [dict(r) for r in rows]}