"""The deterministic step that decides AWARD, RETRY or REJECT (PRODUCT.md, "Recognition").

The model only proposes candidates. Every decision here follows from the CSV,
the thresholds file, the player's location and a blind reading of the photo's
text (a second request with no list of collectibles, so the model has nothing to
expect). When unsure, award nothing.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from clocked import messages
from clocked.catalogue import Catalogue, Item
from clocked.geo import distance_m
from clocked.recognition.schema import (
    Candidate,
    CandidateCheck,
    Location,
    ModelAnswer,
    Outcome,
    Result,
)
from clocked.textmatch import matches

THRESHOLDS_FILE = Path(__file__).resolve().parent / "thresholds.toml"


@dataclass(frozen=True)
class Thresholds:
    high: float
    medium: float

    @classmethod
    def load(cls, path: Path = THRESHOLDS_FILE) -> "Thresholds":
        with open(path, "rb") as handle:
            data = tomllib.load(handle)
        thresholds = cls(high=data["default"]["high"], medium=data["default"]["medium"])
        if not 0 < thresholds.medium <= thresholds.high <= 1:
            raise ValueError(f"thresholds out of order: {thresholds}")
        return thresholds


def check_candidate(
    candidate: Candidate,
    item: Item,
    location: Location | None,
    thresholds: Thresholds,
    blind_lines: list[str] | None = None,
) -> CandidateCheck:
    """Apply one item's verification rules to one candidate.

    A text check passes only when both the candidate's object text and the blind
    reading contain the item's match_text. No blind reading means it fails.

    Location is checked before the text, so a place item's name is only shown to
    a player who is near it, or whose photo shows that name in both readings.
    """

    def result(outcome: Outcome, code: str, distance: float | None = None) -> CandidateCheck:
        return CandidateCheck(
            candidate_id=item.id, outcome=outcome, reason_code=code, distance_m=distance
        )

    if candidate.confidence < thresholds.medium:
        return result(Outcome.REJECT, "low_confidence")

    if item.conflict_text and matches(item.conflict_text, candidate.object_text):
        return result(Outcome.RETRY, "text_conflict")

    object_ok = not item.needs_text or matches(item.match_text, candidate.object_text)
    blind_ok = not item.needs_text or matches(item.match_text, blind_lines or [])
    text_ok = object_ok and blind_ok
    distance = None
    if item.needs_location:
        if location is None:
            return result(Outcome.RETRY, "location_missing")
        if location.accuracy_m > item.radius_m:
            return result(Outcome.RETRY, "location_imprecise")
        distance = distance_m(location.lat, location.lng, item.lat, item.lng)
        if distance > item.radius_m:
            code = "out_of_radius_named" if item.needs_text and text_ok else "out_of_radius"
            return result(Outcome.REJECT, code, distance)

    if not object_ok:
        return result(Outcome.RETRY, "text_missing", distance)
    if not blind_ok:
        return result(Outcome.RETRY, "blind_text_missing", distance)

    if candidate.confidence >= thresholds.high:
        return result(Outcome.AWARD, "passed", distance)

    # Medium confidence. An item checked by both text and location has just had
    # its name read in both readings and the player found within its radius:
    # that is stronger evidence than the model's own certainty.
    if item.needs_text and item.needs_location:
        return result(Outcome.AWARD, "passed_text_and_location", distance)

    return result(Outcome.RETRY, "medium_confidence", distance)


def _choose(checks: list[CandidateCheck], catalogue: Catalogue) -> CandidateCheck:
    """One photo, one discovery: a passing place item, else any pass, else the first."""
    awarded = [check for check in checks if check.outcome is Outcome.AWARD]
    for check in awarded:
        if catalogue[check.candidate_id].is_place:
            return check
    if awarded:
        return awarded[0]
    return checks[0]


def _reads_cypher(cypher: Item, lines: list[str]) -> bool:
    """The lines name this cypher and nothing in its conflict_text (G R inside G R VI)."""
    if not matches(cypher.match_text, lines):
        return False
    return not (cypher.conflict_text and matches(cypher.conflict_text, lines))


def _check_cypher(
    answer: ModelAnswer, chosen: Candidate, catalogue: Catalogue, blind_lines: list[str] | None
) -> tuple[str | None, str | None]:
    """Return (awarded cypher id, reason code). Only called when an item is awarded.

    No confidence threshold: the two readings must agree on the same cypher.
    """
    if answer.cypher_id is None:
        return None, None
    cypher = catalogue.get(answer.cypher_id)
    if cypher is None or not cypher.is_nested:
        return None, "cypher_unknown"
    if cypher.parent_id != chosen.candidate_id:
        return None, "cypher_not_on_parent"
    if not _reads_cypher(cypher, chosen.object_text):
        return None, "cypher_text_missing"
    blind_cyphers = {c.id for c in catalogue.nested_items if _reads_cypher(c, blind_lines or [])}
    if blind_cyphers != {cypher.id}:
        return None, "cypher_blind_disagrees"
    return cypher.id, "cypher_passed"


def verify(
    answer: ModelAnswer,
    catalogue: Catalogue,
    location: Location | None,
    thresholds: Thresholds,
    blind_lines: list[str] | None = None,
) -> Result:
    candidates: list[Candidate] = []
    checks: list[CandidateCheck] = []
    for candidate in answer.candidates:
        if any(seen.candidate_id == candidate.candidate_id for seen in candidates):
            continue  # the same item twice: keep the first, most certain one
        item = catalogue.get(candidate.candidate_id)
        if item is None or item.is_nested:
            checks.append(
                CandidateCheck(
                    candidate_id=candidate.candidate_id,
                    outcome=Outcome.REJECT,
                    reason_code="unknown_item",
                )
            )
        else:
            checks.append(check_candidate(candidate, item, location, thresholds, blind_lines))
        candidates.append(candidate)

    if not checks:
        return Result(
            outcome=Outcome.REJECT,
            message=messages.COULD_NOT_IDENTIFY,
            reason_code="no_candidate",
        )

    chosen = _choose(checks, catalogue)
    item = catalogue.get(chosen.candidate_id)

    # A screen, poster or print of an item is not the item (PRODUCT.md, "Further rules").
    # The message names a type item, but never a place: a postcard must not give away
    # a hidden place's name to someone who is not there.
    if answer.photo_of_picture:
        named = item.name if item and not item.is_place else "it"
        return Result(
            outcome=Outcome.RETRY,
            message=messages.for_check("photo_of_picture", named),
            reason_code="photo_of_picture",
            checks=checks,
        )

    message = messages.for_check(chosen.reason_code, item.name if item else "")

    if chosen.outcome is not Outcome.AWARD:
        return Result(
            outcome=chosen.outcome,
            message=message,
            reason_code=chosen.reason_code,
            checks=checks,
        )

    chosen_candidate = candidates[checks.index(chosen)]
    cypher_id, cypher_code = _check_cypher(answer, chosen_candidate, catalogue, blind_lines)
    return Result(
        outcome=Outcome.AWARD,
        item_id=chosen.candidate_id,
        cypher_id=cypher_id,
        message=message,
        reason_code=chosen.reason_code,
        cypher_reason_code=cypher_code,
        checks=checks,
    )


def needs_blind_read(answer: ModelAnswer, catalogue: Catalogue) -> bool:
    """True when an award could depend on text: a candidate with a text check, or a cypher."""
    if answer.cypher_id is not None:
        return True
    return any(
        (item := catalogue.get(c.candidate_id)) is not None and item.needs_text
        for c in answer.candidates
    )
