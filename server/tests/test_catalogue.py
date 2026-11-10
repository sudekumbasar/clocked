import csv
from pathlib import Path

import pytest

from clocked.catalogue import DEFAULT_CSV, CatalogueError, load_catalogue


def test_real_csv_loads():
    catalogue = load_catalogue()
    assert len(catalogue.items) == 70
    assert len(catalogue.main_items) == 63
    assert {item.parent_id for item in catalogue.nested_items} == {"S02"}


def test_place_items_with_location_have_coordinates_and_radius():
    for item in load_catalogue().items:
        if item.needs_location:
            assert item.is_place and item.radius_m and item.lat is not None


def write_variant(tmp_path: Path, item_id: str, **changes) -> Path:
    rows = list(csv.DictReader(open(DEFAULT_CSV, newline="", encoding="utf-8")))
    for row in rows:
        if row["id"] == item_id:
            row.update(changes)
    path = tmp_path / "variant.csv"
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.mark.parametrize(
    "item_id, changes, message",
    [
        ("P01", {"verification_radius_m": ""}, "verification_radius_m"),
        ("T08", {"verification_radius_m": "75"}, "verification_radius_m"),
        ("P01", {"match_text": ""}, "match_text"),
        ("S01", {"match_text": "TELEPHONE"}, "match_text"),
        ("S08", {"lat": ""}, "lat and lng"),
        ("S01", {"lat": "51.5"}, "type items"),
        ("S01", {"verification": "text"}, "verification"),
        ("S01", {"verification": "vision+smell"}, "verification"),
        ("S01", {"kind": "thing"}, "kind"),
        ("S01", {"rarity": "epic"}, "rarity"),
        ("S01", {"fact": ""}, "fact"),
        ("S01", {"model_hint": ""}, "model_hint"),
        ("C01", {"parent_id": "X99"}, "parent_id"),
        ("C01", {"parent_id": "C02"}, "nested"),
        ("S02", {"id": "S01"}, "duplicate"),
    ],
)
def test_invalid_data_is_refused(tmp_path, item_id, changes, message):
    with pytest.raises(CatalogueError, match=message):
        load_catalogue(write_variant(tmp_path, item_id, **changes))


def test_disabled_set_is_left_out_but_stays_in_the_csv():
    catalogue = load_catalogue(disabled_sets=("royal-cyphers",))
    assert len(catalogue.items) == 63
    assert catalogue.nested_items == []
    assert catalogue.get("C04") is None
    assert load_catalogue().get("C04") is not None


def test_version_1_is_four_categories_of_ten():
    from collections import Counter

    from clocked.config import Settings

    catalogue = load_catalogue(disabled_sets=Settings().disabled_sets)
    assert Counter(item.category for item in catalogue.items) == {
        "London Icons": 10, "Londoner's London": 10, "Pub Crawl": 10, "Film & Free Museums": 10,
    }
    assert catalogue.get("P01") is None and load_catalogue().get("P01") is not None


def test_every_pub_is_checked_by_name_and_location():
    for item in load_catalogue().items:
        if item.category == "Pub Crawl":
            assert item.signals == {"vision", "text", "location"} and item.match_text


def test_app_default_has_no_cyphers():
    from clocked.config import Settings
    from clocked.recognition.prompt import output_schema, system_prompt

    catalogue = load_catalogue(disabled_sets=Settings().disabled_sets)
    assert output_schema(catalogue)["properties"]["cypher_id"] == {"type": "null"}
    assert "Royal cyphers" not in system_prompt(catalogue)
