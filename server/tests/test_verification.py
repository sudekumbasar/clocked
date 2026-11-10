"""Every verification rule in PRODUCT.md, using the real CSV and fixed thresholds."""

import pytest

from clocked import messages
from clocked.catalogue import load_catalogue
from clocked.recognition.schema import Candidate, Location, ModelAnswer, Outcome
from clocked.verification import Thresholds, verify

CATALOGUE = load_catalogue()
T = Thresholds(high=0.85, medium=0.50)

HIGH, MEDIUM, LOW = 0.95, 0.70, 0.30


def at(item_id: str, accuracy_m: float = 10, north_m: float = 0) -> Location:
    """The player's location, optionally some metres north of an item."""
    item = CATALOGUE[item_id]
    return Location(lat=item.lat + north_m / 111_195, lng=item.lng, accuracy_m=accuracy_m)


FAR_AWAY = Location(lat=51.4, lng=0.1, accuracy_m=10)


def cand(item_id: str, confidence: float = HIGH, text: list[str] | None = None) -> Candidate:
    return Candidate(candidate_id=item_id, confidence=confidence, object_text=text or [])


SAME = object()


def run(*candidates, location=None, blind=SAME, **answer_fields):
    """Verify an answer. By default the blind reading agrees with the candidates' object text."""
    answer = ModelAnswer(candidates=list(candidates), **answer_fields)
    if blind is SAME:
        blind = [line for c in candidates for line in c.object_text]
    return verify(answer, CATALOGUE, location, T, blind)


# --- no candidate, confidence -----------------------------------------------


def test_no_candidate_rejects():
    result = run()
    assert result.outcome is Outcome.REJECT
    assert result.reason_code == "no_candidate"
    assert result.message == messages.COULD_NOT_IDENTIFY


def test_low_confidence_rejects():
    result = run(cand("S01", LOW))
    assert (result.outcome, result.reason_code) == (Outcome.REJECT, "low_confidence")
    assert result.item_id is None


def test_medium_confidence_retries_with_name():
    result = run(cand("S01", MEDIUM))
    assert (result.outcome, result.reason_code) == (Outcome.RETRY, "medium_confidence")
    assert result.message == "I think this might be: Red telephone box. Take a closer photo to confirm."


def test_vision_only_item_awards_at_high_confidence():
    result = run(cand("S01", HIGH))
    assert (result.outcome, result.item_id) == (Outcome.AWARD, "S01")
    assert result.message == messages.CLOCKED_IT


def test_threshold_boundaries():
    assert run(cand("S01", 0.85)).outcome is Outcome.AWARD
    assert run(cand("S01", 0.849)).outcome is Outcome.RETRY
    assert run(cand("S01", 0.50)).outcome is Outcome.RETRY
    assert run(cand("S01", 0.499)).outcome is Outcome.REJECT


def test_unknown_or_nested_candidate_rejects():
    assert run(cand("X99")).reason_code == "unknown_item"
    assert run(cand("C06")).reason_code == "unknown_item"


# --- text ---------------------------------------------------------------------


def test_text_item_awards_when_text_on_object_matches():
    result = run(cand("S06", HIGH, ["DEAN STREET W1", "CITY OF WESTMINSTER"]))
    assert (result.outcome, result.item_id) == (Outcome.AWARD, "S06")


def test_text_item_retries_when_text_missing():
    result = run(cand("S06", HIGH, ["DEAN STREET W1"]))
    assert (result.outcome, result.reason_code) == (Outcome.RETRY, "text_missing")


def test_text_elsewhere_in_frame_does_not_count():
    result = run(cand("S06", HIGH, ["DEAN STREET W1"]), other_text=["CITY OF WESTMINSTER"])
    assert result.reason_code == "text_missing"


def test_text_missing_even_with_high_confidence_never_awards():
    assert run(cand("T08", 1.0, [])).outcome is Outcome.RETRY


def test_text_award_needs_the_blind_reading_too():
    sign = cand("S06", HIGH, ["CITY OF WESTMINSTER"])
    assert run(sign, blind=["DEAN STREET"]).reason_code == "blind_text_missing"
    assert run(sign, blind=None).reason_code == "blind_text_missing"
    assert run(sign, blind=["Dean Street W1", "City of Westminster"]).outcome is Outcome.AWARD


def test_vision_only_items_do_not_need_a_blind_reading():
    assert run(cand("S01", HIGH), blind=None).outcome is Outcome.AWARD


# --- conflicting text ---------------------------------------------------------


def test_conflicting_mode_on_roundel_retries():
    result = run(cand("T01", HIGH, ["LONDON OVERGROUND"]))
    assert (result.outcome, result.reason_code) == (Outcome.RETRY, "text_conflict")


def test_other_modes_elsewhere_in_frame_are_ignored():
    result = run(cand("T01", HIGH, ["HIGHBURY & ISLINGTON"]), other_text=["OVERGROUND", "ELIZABETH LINE"])
    assert (result.outcome, result.item_id) == (Outcome.AWARD, "T01")


def test_bus_stop_roundel_conflict():
    assert run(cand("T04", HIGH, ["UNDERGROUND"])).reason_code == "text_conflict"
    assert run(cand("T04", HIGH, ["BUS STOP"])).outcome is Outcome.AWARD


# --- location -----------------------------------------------------------------


PLAQUE = cand("P01", HIGH, ["JIMI HENDRIX", "1942-1970", "GUITARIST AND SONGWRITER", "LIVED HERE"])


def test_plaque_awards_near_address():
    result = run(PLAQUE, location=at("P01"))
    assert (result.outcome, result.item_id) == (Outcome.AWARD, "P01")


def test_plaque_without_location_retries():
    result = run(PLAQUE, location=None)
    assert (result.outcome, result.reason_code) == (Outcome.RETRY, "location_missing")
    assert result.message == messages.NEED_LOCATION


def test_imprecise_location_retries():
    result = run(PLAQUE, location=at("P01", accuracy_m=76))
    assert (result.outcome, result.reason_code) == (Outcome.RETRY, "location_imprecise")
    assert run(PLAQUE, location=at("P01", accuracy_m=75)).outcome is Outcome.AWARD


def test_radius_boundary():
    assert run(PLAQUE, location=at("P01", north_m=70)).outcome is Outcome.AWARD
    assert run(PLAQUE, location=at("P01", north_m=80)).outcome is Outcome.REJECT


def test_plaque_with_matching_text_outside_radius_gets_named_message():
    result = run(PLAQUE, location=FAR_AWAY)
    assert (result.outcome, result.reason_code) == (Outcome.REJECT, "out_of_radius_named")
    assert result.message == "This looks like Jimi Hendrix, but you don't seem to be near it."


def test_named_message_only_when_blind_reading_has_the_name():
    # First Haiku run: "JOHN LENNON" written on a plaque too small to read.
    invented = cand("P03", HIGH, ["JOHN LENNON"])
    result = run(invented, location=at("P01"), blind=["N.PEAL"])
    assert (result.outcome, result.reason_code) == (Outcome.REJECT, "out_of_radius")
    assert "Lennon" not in result.message


def test_plaque_near_address_with_unreadable_blind_text_retries():
    result = run(PLAQUE, location=at("P01"), blind=[])
    assert (result.outcome, result.reason_code) == (Outcome.RETRY, "blind_text_missing")


def test_plaque_without_matching_text_outside_radius_gets_generic_message():
    result = run(cand("P01", HIGH, ["SOMEONE ELSE"]), location=FAR_AWAY)
    assert (result.outcome, result.reason_code) == (Outcome.REJECT, "out_of_radius")
    assert result.message == messages.COULD_NOT_IDENTIFY


def test_place_without_text_outside_radius_does_not_reveal_name():
    result = run(cand("S08", HIGH), location=FAR_AWAY)
    assert (result.outcome, result.reason_code) == (Outcome.REJECT, "out_of_radius")
    assert "Abbey Road" not in result.message


def test_place_item_name_not_revealed_when_far_and_text_missing():
    # Location is checked before text, so a far-away plaque with unreadable text gives nothing away.
    result = run(cand("P01", HIGH, []), location=FAR_AWAY)
    assert "Hendrix" not in result.message


def test_wider_radius_from_csv():
    # Earl's Court police box has a 200 m radius in the CSV.
    assert run(cand("S10", HIGH), location=at("S10", north_m=150)).outcome is Outcome.AWARD


def test_underground_place_items_never_need_location():
    t08 = cand("T08", HIGH, ["FRANK PICK"])
    assert run(t08, location=None).outcome is Outcome.AWARD
    assert run(cand("T09", HIGH), location=FAR_AWAY).outcome is Outcome.AWARD


def test_type_items_ignore_location():
    assert run(cand("S01", HIGH), location=FAR_AWAY).outcome is Outcome.AWARD


def test_text_checked_after_location_near_address():
    result = run(cand("P01", HIGH, ["HANDEL"]), location=at("P01"))
    assert (result.outcome, result.reason_code) == (Outcome.RETRY, "text_missing")


# --- overlapping items --------------------------------------------------------


def test_abbey_road_beats_belisha_beacon_when_near():
    result = run(cand("S05", HIGH), cand("S08", 0.90), location=at("S08"))
    assert result.item_id == "S08"


def test_belisha_beacon_awarded_at_any_other_crossing():
    result = run(cand("S08", HIGH), cand("S05", 0.90), location=FAR_AWAY)
    assert (result.outcome, result.item_id) == (Outcome.AWARD, "S05")


def test_aldwych_beats_leslie_green_when_near():
    result = run(cand("T06", HIGH), cand("T10", 0.90), location=at("T10"))
    assert result.item_id == "T10"


def test_frank_pick_memorial_beats_its_roundel():
    roundel = cand("T01", HIGH, ["FRANK PICK"])
    memorial = cand("T08", 0.90, ["FRANK PICK", "BEAUTY < IMMORTALITY"])
    result = run(roundel, memorial)
    assert result.item_id == "T08"
    assert result.checks[0].reason_code == "text_conflict"


def test_two_type_items_most_certain_passing_one_wins():
    result = run(cand("S04", MEDIUM), cand("S03", HIGH))
    assert result.item_id == "S03"


def test_duplicate_candidate_is_ignored():
    # Haiku once returned the same post box twice with different text.
    result = run(post_box(["POST OFFICE"]), post_box(["E II R"]),
                 cypher_id="C06", cypher_confidence=0.99)
    assert len(result.checks) == 1
    assert (result.item_id, result.cypher_id) == ("S02", None)


def test_nothing_passes_uses_first_candidate():
    result = run(cand("S04", MEDIUM), cand("S03", LOW))
    assert (result.outcome, result.reason_code) == (Outcome.RETRY, "medium_confidence")
    assert "double-decker" in result.message


# --- post boxes and cyphers ---------------------------------------------------


def post_box(text, confidence=HIGH):
    return cand("S02", confidence, text)


def test_post_box_and_cypher_awarded_together():
    result = run(post_box(["E II R"]), cypher_id="C06", cypher_confidence=0.97)
    assert (result.outcome, result.item_id, result.cypher_id) == (Outcome.AWARD, "S02", "C06")


def test_cypher_has_no_confidence_threshold_when_readings_agree():
    result = run(post_box(["E II R"]), cypher_id="C06", cypher_confidence=0.60)
    assert result.cypher_id == "C06"


def test_cypher_needs_the_blind_reading_to_agree():
    result = run(post_box(["E II R"]), cypher_id="C06", cypher_confidence=0.99, blind=["E VII R"])
    assert (result.item_id, result.cypher_id) == ("S02", None)
    assert result.cypher_reason_code == "cypher_blind_disagrees"


def test_cypher_without_a_blind_reading_is_not_awarded():
    result = run(post_box(["E II R"]), cypher_id="C06", cypher_confidence=0.99, blind=None)
    assert (result.item_id, result.cypher_id) == ("S02", None)


def test_blind_reading_naming_two_cyphers_is_not_agreement():
    result = run(post_box(["E II R"]), cypher_id="C06", cypher_confidence=0.99,
                 blind=["E II R", "G R"])
    assert result.cypher_reason_code == "cypher_blind_disagrees"


def test_haiku_case_wrong_cypher_text_is_caught_by_blind_reading():
    # First Haiku run: an E VII R box reported as C06 with "E II R" as object text.
    result = run(post_box(["E II R"]), cypher_id="C06", cypher_confidence=0.9, blind=["VIII"])
    assert result.cypher_id is None


def test_cypher_written_with_numeral_last():
    # Larger models write the E VII R monogram as "E R VII".
    result = run(post_box(["E R VII"]), cypher_id="C02", cypher_confidence=0.8, blind=["E R VII"])
    assert result.cypher_id == "C02"


def test_cypher_text_must_be_on_post_box():
    result = run(post_box([]), cypher_id="C06", cypher_confidence=0.99, other_text=["E II R"])
    assert (result.item_id, result.cypher_id) == ("S02", None)
    assert result.cypher_reason_code == "cypher_text_missing"


def test_edward_vii_never_awards_edward_viii():
    result = run(post_box(["E VII R"]), cypher_id="C04", cypher_confidence=0.99)
    assert result.cypher_id is None


def test_george_vi_never_awards_george_v():
    result = run(post_box(["G VI R"]), cypher_id="C03", cypher_confidence=0.99)
    assert result.cypher_id is None


def test_no_cypher_when_post_box_not_awarded():
    result = run(post_box(["E II R"], MEDIUM), cypher_id="C06", cypher_confidence=0.99)
    assert (result.outcome, result.cypher_id) == (Outcome.RETRY, None)


def test_cypher_on_something_else_does_not_count():
    result = run(cand("S10", HIGH, ["POLICE BOX", "E II R"]), cypher_id="C06",
                 cypher_confidence=0.99, location=at("S10"))
    assert (result.item_id, result.cypher_id) == ("S10", None)
    assert result.cypher_reason_code == "cypher_not_on_parent"


def test_cypher_only_counts_when_post_box_is_the_awarded_item():
    # Abbey Road wins over the post box in the same photo, so the cypher is not awarded.
    result = run(post_box(["E II R"]), cand("S08", 0.90), cypher_id="C06",
                 cypher_confidence=0.99, location=at("S08"))
    assert (result.item_id, result.cypher_id) == ("S08", None)


def test_post_box_without_cypher():
    result = run(post_box([]))
    assert (result.item_id, result.cypher_id, result.cypher_reason_code) == ("S02", None, None)


@pytest.mark.parametrize("cypher_id, text", [
    ("C01", "VR"), ("C02", "E VII R"), ("C03", "G R"), ("C04", "E VIII R"),
    ("C05", "G VI R"), ("C06", "E.II.R"), ("C07", "C III R"),
])
def test_every_cypher_can_be_awarded(cypher_id, text):
    assert run(post_box([text]), cypher_id=cypher_id, cypher_confidence=0.99).cypher_id == cypher_id


@pytest.mark.parametrize("read", ["G R VI", "G VI R"])
def test_george_vi_written_either_way_never_awards_george_v(read):
    result = run(post_box([read]), cypher_id="C03", cypher_confidence=0.99, blind=[read])
    assert result.cypher_id is None


def test_george_vi_numeral_last_awards_c05():
    result = run(post_box(["G R VI"]), cypher_id="C05", cypher_confidence=0.9, blind=["G R VI"])
    assert result.cypher_id == "C05"


# --- medium confidence with both the name and the location ---------------------
# B03 The George Inn: vision+text+location, match_text GEORGE INN|THE GEORGE, 75 m.


def test_pub_awards_at_medium_confidence_when_name_and_location_pass():
    result = run(cand("B03", MEDIUM, ["THE GEORGE"]), location=at("B03"))
    assert (result.outcome, result.item_id, result.reason_code) == (
        Outcome.AWARD, "B03", "passed_text_and_location")
    assert result.message == messages.CLOCKED_IT


def test_pub_at_medium_confidence_retries_when_blind_reading_misses_the_name():
    result = run(cand("B03", MEDIUM, ["THE GEORGE"]), location=at("B03"), blind=["NICHOLSONS"])
    assert (result.outcome, result.reason_code) == (Outcome.RETRY, "blind_text_missing")


def test_pub_at_medium_confidence_retries_when_the_object_text_misses_the_name():
    result = run(cand("B03", MEDIUM, ["PARLIAMENT BAR"]), location=at("B03"), blind=["THE GEORGE"])
    assert (result.outcome, result.reason_code) == (Outcome.RETRY, "text_missing")


def test_pub_at_medium_confidence_outside_the_radius_rejects():
    result = run(cand("B03", MEDIUM, ["THE GEORGE"]), location=at("B03", north_m=200))
    assert (result.outcome, result.reason_code) == (Outcome.REJECT, "out_of_radius_named")


def test_pub_at_medium_confidence_without_location_retries():
    result = run(cand("B03", MEDIUM, ["THE GEORGE"]))
    assert (result.outcome, result.reason_code) == (Outcome.RETRY, "location_missing")


def test_pub_at_low_confidence_still_rejects():
    result = run(cand("B03", LOW, ["THE GEORGE"]), location=at("B03"))
    assert (result.outcome, result.reason_code) == (Outcome.REJECT, "low_confidence")


def test_place_without_a_text_check_still_needs_high_confidence():
    # F01 Platform 9 3/4 is vision+location: the shop next door reached 0.80 in testing.
    result = run(cand("F01", MEDIUM), location=at("F01"))
    assert (result.outcome, result.reason_code) == (Outcome.RETRY, "medium_confidence")


def test_type_item_with_a_text_check_still_needs_high_confidence():
    # S06 (retired) is vision+text with no location.
    result = run(cand("S06", MEDIUM, ["CITY OF WESTMINSTER"]))
    assert (result.outcome, result.reason_code) == (Outcome.RETRY, "medium_confidence")


# --- a picture of an item is not the item --------------------------------------


def test_photo_of_a_screen_never_awards_a_type_item():
    result = run(cand("S04", HIGH), photo_of_picture=True)
    assert (result.outcome, result.reason_code, result.item_id) == (Outcome.RETRY, "photo_of_picture", None)
    assert result.message == "This looks like a picture of Red double-decker bus, not the real thing. Take a photo of the real one."


def test_photo_of_a_poster_never_awards_a_place_even_there():
    result = run(cand("L06", HIGH), location=at("L06"), photo_of_picture=True)
    assert (result.outcome, result.reason_code) == (Outcome.RETRY, "photo_of_picture")


def test_a_picture_never_gives_away_a_hidden_place_name():
    result = run(cand("B10", HIGH, ["THE SPANIARDS INN"]), location=FAR_AWAY, photo_of_picture=True)
    assert "Spaniards" not in result.message
    assert result.message == "This looks like a picture of it, not the real thing. Take a photo of the real one."


def test_photo_of_a_picture_of_a_pub_sign_never_awards():
    result = run(cand("B03", MEDIUM, ["THE GEORGE"]), location=at("B03"), photo_of_picture=True)
    assert result.outcome is not Outcome.AWARD


def test_a_real_object_still_awards():
    result = run(cand("S04", HIGH), photo_of_picture=False)
    assert (result.outcome, result.item_id) == (Outcome.AWARD, "S04")


def test_no_candidate_stays_a_reject_even_for_a_picture():
    assert run(photo_of_picture=True).reason_code == "no_candidate"
