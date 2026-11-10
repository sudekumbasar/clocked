"""The test script end to end, with the fake provider."""

import csv
import json

import pytest

from conftest import make_photo
from tools import score_photos

FIELDS = score_photos.LABEL_FIELDS


def write_set(tmp_path, rows, answers):
    photos = tmp_path / "photos"
    photos.mkdir()
    for row in rows:
        (photos / row["file"]).write_bytes(make_photo(size=(400, 300)))
    labels = tmp_path / "labels.csv"
    with open(labels, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDS})
    fake = tmp_path / "fake.json"
    fake.write_text(json.dumps(answers))
    return photos, labels, fake


def cand(item_id, confidence=0.95, text=()):
    return {"candidate_id": item_id, "confidence": confidence, "object_text": list(text)}


def run(tmp_path, rows, answers, *extra):
    photos, labels, fake = write_set(tmp_path, rows, answers)
    argv = ["--provider", "fake", "--fake-answers", str(fake), "--photos", str(photos),
            "--labels", str(labels), "--runs", str(tmp_path / "runs"), *extra]
    return score_photos.main(argv)


ROWS = [
    {"file": "s01_phonebox_01.jpg", "expected_id": "S01", "clear": "y"},
    {"file": "s02_postbox_c06_01.jpg", "expected_id": "S02", "expected_cypher": "C06", "clear": "y"},
    {"file": "b01_churchill_arms_01.jpg", "expected_id": "B01", "lat": "51.50688", "lng": "-0.19487"},
    {"file": "neg_red_bin_01.jpg"},
]
GOOD = {
    "s01_phonebox_01.jpg": {"candidates": [cand("S01")]},
    "s02_postbox_c06_01.jpg": {"candidates": [cand("S02", text=["E II R"])],
                               "cypher_id": "C06", "cypher_confidence": 0.98,
                               "blind_lines": ["E II R"]},
    "b01_churchill_arms_01.jpg": {"candidates": [cand("B01", text=["THE CHURCHILL ARMS"])],
                                  "blind_lines": ["THE CHURCHILL ARMS"]},
}


def test_clean_run_exits_zero_and_saves_files(tmp_path, capsys):
    assert run(tmp_path, ROWS, GOOD) == 0
    report = capsys.readouterr().out
    assert "## Wrong awards: 0" in report
    assert "| Positives | 3 | 0 | 0 | 0 | 0 |" in report
    assert "s02_postbox_c06_01.jpg | C06 | C06 | - |" in report  # named, but the set is off
    assert "| Negatives | 0 | 0 | 0 | 1 | 0 |" in report
    assert "2/2 (100%)" in report
    (run_dir,) = (tmp_path / "runs").iterdir()
    assert {p.name for p in run_dir.iterdir()} == {"summary.md", "answers.jsonl", "results.csv"}


def test_wrong_award_on_negative_fails_the_run(tmp_path, capsys):
    answers = dict(GOOD, **{"neg_red_bin_01.jpg": {"candidates": [cand("S02")]}})
    assert run(tmp_path, ROWS, answers) == 1
    report = capsys.readouterr().out
    assert "## Wrong awards: 1" in report
    assert "neg_red_bin_01.jpg: awarded S02, expected nothing" in report


def test_switched_off_cyphers_are_never_awarded(tmp_path, capsys):
    # Royal Cyphers are not in version 1: even a model naming one awards only the box.
    answers = dict(GOOD, **{"s02_postbox_c06_01.jpg": {
        "candidates": [cand("S02", text=["E VII R"])], "cypher_id": "C02", "cypher_confidence": 0.99,
        "blind_lines": ["E VII R"]}})
    assert run(tmp_path, ROWS, answers) == 0
    assert "+ C0" not in capsys.readouterr().out


def test_also_ok_is_not_a_wrong_award(tmp_path):
    rows = [{"file": "t10_aldwych_01.jpg", "expected_id": "T10", "also_ok": "T06",
             "lat": "51.51215", "lng": "-0.11595"}]
    assert run(tmp_path, rows, {"t10_aldwych_01.jpg": {"candidates": [cand("T06")]}}) == 0


def test_rules_only_rescores_without_calls(tmp_path, capsys):
    run(tmp_path, ROWS, GOOD)
    (first_run,) = (tmp_path / "runs").iterdir()
    capsys.readouterr()
    code = score_photos.main(["--labels", str(tmp_path / "labels.csv"), "--photos",
                              str(tmp_path / "photos"), "--runs", str(tmp_path / "runs"),
                              "--rules-only", str(first_run)])
    assert code == 0
    assert "Re-scored from saved answers" in capsys.readouterr().out


def test_unknown_label_id_stops(tmp_path):
    with pytest.raises(SystemExit):
        run(tmp_path, [{"file": "x.jpg", "expected_id": "Z99"}], {})


def test_budget_guard_stops_before_spending(tmp_path, monkeypatch):
    ledger = tmp_path / "ledger.csv"
    ledger.write_text("time_utc,provider,model,input_tokens,output_tokens,cost_usd,source\n"
                      "2026-10-06T00:00:00+00:00,anthropic,claude-haiku-4-5,0,0,7.999,api\n")
    monkeypatch.setenv("CLOCKED_COST_LEDGER", str(ledger))
    photos, labels, _ = write_set(tmp_path, ROWS, {})
    with pytest.raises(SystemExit, match="past \\$8.00"):
        score_photos.main(["--provider", "anthropic", "--photos", str(photos),
                           "--labels", str(labels), "--runs", str(tmp_path / "runs")])
