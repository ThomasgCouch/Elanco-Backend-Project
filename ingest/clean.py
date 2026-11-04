"""Clean and preprocess the data for ingestion."""

import json
import os
from collections import Counter, defaultdict
from datetime import datetime

RAW_PATH = os.path.join ("data", "raw_sightings.json")
CLEAN_PATH = os.path.join ("data", "clean_sightings.json")
REQUIRED_FIELDS = ["id", "date", "location", "species"]

def normalise_text(value):
    """Trim and collapse whitespace; return None for empty or non-string values."""
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split()) # Remove extra whitespace
    return cleaned or None 

def parse_date(value):
    """Parse an ISO 8601 date string into a datetime object. Return None for invalid formats."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))  # Handle UTC 'Z' suffix
    except ValueError:
        return None
    

def build_canonical_names(values):
    """Map each case-insensitive variant to its most common spelling."""
    counts_by_key = defaultdict(Counter)
    for v in values:
        if v:
            counts_by_key[v.casefold()][v] += 1
    return {key: counts.most_common(1)[0][0] for key, counts in counts_by_key.items()}


def clean(records):
    """Return (clean_records, report) for a list of raw sighting dicts"""
    report = Counter()
    report["raw_records"] = len(records)
    now = datetime.now()
    
    valid = []
    for record in records:
        if not isinstance(record, dict):
            report["invalid_record_type"] += 1
            continue
        
        tidy = {
            "id": normalise_text(record.get("id")),
            "date": record.get("date"),
            "location": normalise_text(record.get("location")),
            "species": normalise_text(record.get("species")),
            "latinName": normalise_text(record.get("latinName")),
        }
        
        missing = [f for f in REQUIRED_FIELDS if not tidy[f]]
        if missing:
            report[f"dropped_missing_{missing[0]}"] += 1
            continue
        
        parsed = parse_date(tidy["date"])
        if parsed is None:
            report["dropped_invalid_date"] += 1
            continue
        if parsed.replace(tzinfo=None) > now:
            report["dropped_future_date"] += 1
            continue
        tidy["date"] = parsed.replace(tzinfo=None).isoformat()  # Store as ISO string without timezone
        
        if record.get("location") != tidy["location"] or record.get("species") != tidy["species"]:
            report["normalised_text"] += 1
        
        valid.append(tidy)
    
    #Make capitals consistent for location and species names    
    location_names = build_canonical_names([r["location"] for r in valid])
    species_names = build_canonical_names([r["species"] for r in valid])
    for r in valid:
        for field, names in [("location", location_names), ("species", species_names)]:
            canonical = names.get(r[field].casefold())
            if canonical and canonical != r[field]:
                report[f"canonicalised_{field}"] += 1
                r[field] = canonical

    #Remove dupilcates based on id, keeping the first occurrence
    seen_ids = set()
    seen_content = set()
    cleaned = []
    for r in valid:
        if r["id"] in seen_ids:
            report["dropped_duplicate_id"] += 1
            continue
        content_key = (r["date"], r["location"], r["species"])
        if content_key in seen_content:
            report["dropped_duplicate_content"] += 1
            continue
        seen_ids.add(r["id"])
        seen_content.add(content_key)
        cleaned.append(r)

    report["cleaned_records"] = len(cleaned)
    return cleaned, report


def main():
    with open(RAW_PATH, encoding="utf-8") as f:
        raw = json.load(f)
        
    cleaned, report = clean(raw)
    
    with open(CLEAN_PATH, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)
        
    print("Cleaning report:")
    for key, value in report.items():
        print(f"{key}: {value}")
    
    print("\nLocation after cleaning:")
    for name, count in Counter(r["location"] for r in cleaned).most_common():
        print(f"{name}: {count}")

    print ("\nSpecies after cleaning:")
    for name, count in Counter(r["species"] for r in cleaned).most_common():
        print(f"{name}: {count}")
    
    print (f"\nSaved {len(cleaned)} cleaned sightings to {CLEAN_PATH}")


if __name__ == "__main__":
    main()