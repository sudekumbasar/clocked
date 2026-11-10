"""Sequential and parallel blind reading."""

import pytest

from clocked.catalogue import load_catalogue
from clocked.recognition.fake_provider import FakeProvider
from clocked.recognition.pipeline import Recogniser

CATALOGUE = load_catalogue()
PLAQUE = {"candidates": [{"candidate_id": "P01", "confidence": 0.95, "object_text": ["HENDRIX"]}]}
BOX = {"candidates": [{"candidate_id": "S01", "confidence": 0.95}]}
CYPHER = {"candidates": [{"candidate_id": "S02", "confidence": 0.95, "object_text": ["E II R"]}],
          "cypher_id": "C06", "cypher_confidence": 0.9}


def run(mode, answers, filename, main_reads=None, reader_reads=None):
    main = FakeProvider(answers, main_reads or {})
    reader = FakeProvider({}, reader_reads or {})
    out = Recogniser(main, reader, mode).run(b"img", "image/jpeg", CATALOGUE, filename)
    return out, main, reader


def test_sequential_reads_only_when_needed():
    out, _, _ = run("sequential", {"a": BOX}, "a", reader_reads={"a": ["TELEPHONE"]})
    assert out.blind_lines is None and len(out.usages) == 1


@pytest.mark.parametrize("answer", [PLAQUE, CYPHER])
def test_sequential_reads_for_text_items_and_cyphers(answer):
    out, _, _ = run("sequential", {"a": answer}, "a", reader_reads={"a": ["X"]})
    assert out.blind_lines == ["X"] and len(out.usages) == 2


def test_parallel_always_reads():
    out, _, _ = run("parallel", {"a": BOX}, "a", reader_reads={"a": ["TELEPHONE"]})
    assert out.blind_lines == ["TELEPHONE"] and len(out.usages) == 2


def test_reader_can_be_a_different_provider():
    out, _, _ = run("sequential", {"a": PLAQUE}, "a", main_reads={"a": ["MAIN"]},
                    reader_reads={"a": ["READER"]})
    assert out.blind_lines == ["READER"]


def test_unknown_mode_is_refused():
    with pytest.raises(ValueError):
        Recogniser(FakeProvider(), FakeProvider(), "sometimes")
