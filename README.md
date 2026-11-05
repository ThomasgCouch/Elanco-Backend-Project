# UK Tick Sightings Backend

A backend MVP for a UK tick sightings tracker, built for the Elanco Placement Programme technical task (backend).

It pulls tick sighting data from the Elanco Tick Sightings API, cleans and validates it, stores it in a local database, and serves it through a REST API with search, filtering and reporting.

**Author:** Thomas Geddes Couch

---

## Features

- **Reliable data ingestion.** Fetches all sightings from the Elanco API, retrying with exponential backoff on rate limits (429), server errors (5xx) and network failures.
- **Data cleaning and validation.** Removes duplicates, drops incomplete or invalid records, tidies whitespace and makes city and species names consistent. Every run prints a report of what was changed or dropped.
- **Regional grouping.** Each city is mapped to its UK region (for example Manchester and Liverpool to the North West), so reports work by city or by region.
- **Search and filtering.** Filter sightings by date range, city, region and species. Matching is case-insensitive, and results are paginated.
- **Reporting endpoints.** Sightings per region, city or species, and trends over time grouped by week or month.
- **Clear error handling.** Meaningful HTTP status codes and messages for invalid input, unknown records and a missing database.
- **Automated tests.** 15 tests covering the cleaning logic and every API endpoint.

---

## How it works

The project has two parts: a **data pipeline** that prepares the data, and an **API** that serves it.

1. **Fetch** (`ingest/fetch.py`) downloads every sighting from the Elanco Tick Sightings API, retrying with backoff if the API fails, and saves the raw response to `data/raw_sightings.json`.
2. **Clean** (`ingest/clean.py`) validates each record, tidies names and removes duplicates, then saves the result to `data/clean_sightings.json`.
3. **Load** (`ingest/load.py`) adds a UK region to each sighting and stores everything in a SQLite database, `data/sightings.db`.
4. **Serve** (`app/main.py`) is a FastAPI app that answers search and reporting requests from that database.

The pipeline runs **once** to build a local copy of the data, and the API then serves every request from that copy. I chose this design deliberately:

- **It avoids the rate limit.** The Elanco API returns 429 errors under load. Calling it on every user request would make my API slow and unreliable.
- **It stays available.** If the Elanco API goes down, my API keeps serving the last good data.
- **Data is cleaned once, in one place.** Every endpoint works from the same validated data, so results are consistent.

---

## Tech stack

| Tool | Why I chose it |
|---|---|
| **Python** | Clear and quick to write, with excellent libraries for data handling. |
| **FastAPI** | Validates query parameters automatically, returns clear errors for bad input, and generates interactive documentation at `/docs`. |
| **SQLite** | Built into Python with no server to set up, and easily fast enough for this dataset. Indexes on the filtered columns keep queries quick. |
| **requests** | A simple, reliable HTTP client for calling the Elanco API. |
| **pytest** | Concise, readable tests. FastAPI's test client lets me test endpoints against a temporary database. |

---

## Getting started

### Prerequisites

- Python 3.10 or newer
- Git

### 1. Clone and set up

```bash
git clone https://github.com/ThomasgCouch/Elanco-Backend-Project.git
cd Elanco-Backend-Project
python -m venv .venv
```

Activate the virtual environment:

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 2. Build the database

```bash
python -m ingest.pipeline
```

This fetches the data from the Elanco API, cleans it and loads it into `data/sightings.db`. The `data/` folder is git-ignored, so the source data is never committed to the repository.

You can also run each stage on its own:

```bash
python -m ingest.fetch   # download raw data
python -m ingest.clean   # clean it and print a report
python -m ingest.load    # load it into SQLite
```

### 3. Start the API

```bash
uvicorn app.main:app --reload
```

Then open **http://127.0.0.1:8000/docs** for interactive documentation, where you can try every endpoint in the browser.

### 4. Run the tests

```bash
python -m pytest -v
```

---

## API endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Service status and number of sightings loaded |
| GET | `/sightings` | Search and filter sightings, with pagination |
| GET | `/sightings/{id}` | A single sighting by ID |
| GET | `/stats/counts` | Number of sightings grouped by region, location or species |
| GET | `/stats/trends` | Sightings over time, grouped by week or month |

### Filters

`/sightings`, `/stats/counts` and `/stats/trends` share the same filters, so they behave consistently.

| Parameter | Example | Notes |
|---|---|---|
| `start` | `2024-06-01` | Earliest date, inclusive |
| `end` | `2024-08-31` | Latest date, inclusive |
| `location` | `london` | City name, case-insensitive |
| `region` | `North West` | UK region, case-insensitive |
| `species` | `marsh tick` | Species name, case-insensitive |
| `limit` / `offset` | `50` / `0` | Pagination for `/sightings` (maximum 500 per page) |

### Example requests

```
GET /sightings?location=london
GET /sightings?start=2024-06-01&end=2024-08-31&species=marsh tick
GET /stats/counts?group_by=region
GET /stats/trends?interval=month&region=Scotland
```

### Example response: `/stats/counts?group_by=region`

```json
{
  "group_by": "region",
  "results": [
    { "name": "East Midlands", "sightings": 156 },
    { "name": "Scotland", "sightings": 151 },
    { "name": "North West", "sightings": 145 }
  ]
}
```

---

## Data handling decisions

### What the cleaning step does

| Problem | How it's handled |
|---|---|
| Missing `id`, `date`, `location` or `species` | Record dropped and counted in the report |
| Date that can't be parsed | Record dropped |
| Date in the future | Record dropped |
| Extra whitespace (`" London "`) | Trimmed |
| Inconsistent capitalisation (`london`, `LONDON`) | Unified to the most common spelling in the data |
| Duplicate IDs | First occurrence kept |
| Same date, location and species under different IDs | Treated as a double submission and dropped |

### What I found

On the current dataset (1,000 sightings across 14 cities and 5 species, from 2023 to 2024), the cleaning step found **no invalid records**. The validation is still important: it protects every endpoint if the source data degrades, which is likely with crowdsourced reports. The tests in `tests/test_clean.py` prove each rule works using deliberately messy data.

### Judgement calls

- **Dropping same-content duplicates** assumes two identical reports (same time, city and species) are a double submission rather than two separate ticks. With crowdsourced data I think that's the safer assumption, but it's a trade-off.
- **Canonical names come from the data itself.** Choosing the most common spelling avoids hard-coding a list of cities that would need updating.
- **The load step is idempotent.** It uses an upsert keyed on the sighting ID, so the pipeline can be re-run any number of times without creating duplicates.

---

## Error handling

| Situation | Response |
|---|---|
| Elanco API rate limits or fails (429, 5xx, network error) | Retried up to 6 times with exponential backoff, respecting `Retry-After` if sent |
| Elanco API returns an unexpected status (e.g. 404) | Fails immediately with a clear message, since retrying won't help |
| `start` is after `end` | `400 Bad Request` with an explanation |
| Badly formatted date or out-of-range `limit` | `422 Unprocessable Entity` from FastAPI's validation |
| Unknown sighting ID | `404 Not Found` |
| Database hasn't been built yet | `503 Service Unavailable`, telling you to run the pipeline |

All user input is passed to SQL through parameterised queries, which prevents SQL injection.

---

## Project structure

```
Elanco-Backend-Project/
├── app/
│   └── main.py          # FastAPI app and endpoints
├── ingest/
│   ├── fetch.py         # Fetch from the Elanco API with retries
│   ├── clean.py         # Validate, normalise and de-duplicate
│   ├── regions.py       # City to UK region mapping
│   ├── load.py          # SQLite schema and loading
│   └── pipeline.py      # Runs fetch, clean and load in one command
├── tests/
│   ├── test_clean.py    # Cleaning rules with messy data
│   └── test_api.py      # Endpoint behaviour and error cases
├── data/                # Generated data and database (git-ignored)
├── requirements.txt
└── README.md
```

---

## What I'd improve with more time

- **Scheduled refreshes.** Run the pipeline automatically (for example nightly) so the data stays current, and fetch only new records rather than everything.
- **PostgreSQL for production.** SQLite is ideal for an MVP, but a production service with many users would benefit from PostgreSQL.
- **Accepting new sightings.** A `POST /sightings` endpoint with validation, so users could report ticks directly.
- **Caching.** Cache the report endpoints, since their results only change when new data is loaded.
- **Deployment.** Containerise the app with Docker and deploy it, with logging and monitoring.
- **Smarter insights.** Detect unusual spikes in sightings per city, or forecast seasonal activity to warn pet owners ahead of peak tick season.
