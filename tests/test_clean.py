"""Unit tests for the cleaning step, using deliberately messy data."""

from ingest.clean import clean, normalise_text, parse_date


def make(id="a1", date="2025-08-14T17:30:00", location="London", species="Marsh tick"):
    return {"id": id, "date": date, "location": location, "species": species, "latinName": "Ixodes"}


def test_normalise_text_trims_and_collapses_whitespace():
    assert normalise_text("  New   Forest ") == "New Forest"
    assert normalise_text("   ") is None
    assert normalise_text(None) is None


def test_parse_date_handles_valid_and_invalid():
    assert parse_date("2025-08-14T17:30:00") is not None
    assert parse_date("2025-08-14T17:30:00Z") is not None
    assert parse_date("not a date") is None
    assert parse_date(None) is None


def test_drops_records_missing_required_fields():
    records = [make(), make(id="a2", location=""), make(id="a3", species=None)]
    cleaned, report = clean(records)
    assert len(cleaned) == 1
    assert report["dropped_missing_location"] == 1
    assert report["dropped_missing_species"] == 1


def test_drops_invalid_and_future_dates():
    records = [make(), make(id="a2", date="yesterday"), make(id="a3", date="2999-01-01T00:00:00")]
    cleaned, report = clean(records)
    assert len(cleaned) == 1
    assert report["dropped_invalid_date"] == 1
    assert report["dropped_future_date"] == 1


def test_removes_duplicate_ids_and_duplicate_content():
    records = [
        make(),
        make(),                                   # same id
        make(id="a2"),                            # same details, different id
        make(id="a3", date="2025-08-15T09:00:00"),
    ]
    cleaned, report = clean(records)
    assert len(cleaned) == 2
    assert report["dropped_duplicate_id"] == 1
    assert report["dropped_duplicate_content"] == 1


def test_makes_capitalisation_consistent():
    records = [
        make(id="a1", location="London"),
        make(id="a2", location="London", date="2025-08-15T09:00:00"),
        make(id="a3", location="london", date="2025-08-16T09:00:00"),
    ]
    cleaned, _ = clean(records)
    assert {r["location"] for r in cleaned} == {"London"}


def test_skips_non_dict_records():
    cleaned, report = clean([make(), "garbage", 42])
    assert len(cleaned) == 1
    assert report["invalid_record_type"] == 2