import pytest

from clocked.catalogue import load_catalogue
from clocked.textmatch import matches

CATALOGUE = load_catalogue()


def match_text(item_id: str) -> str:
    return CATALOGUE[item_id].match_text


# Royal cyphers, using the real match_text values from the CSV.


@pytest.mark.parametrize("read", ["E II R", "EIIR", "E.II.R", "e ii r", "E. II. R."])
def test_eiir_spellings_match_c06(read):
    assert matches(match_text("C06"), [read])


@pytest.mark.parametrize("read", ["G R", "GR", "G.R."])
def test_gr_matches_c03(read):
    assert matches(match_text("C03"), [read])


@pytest.mark.parametrize("read", ["G VI R", "GVIR", "G.VI.R"])
def test_gvir_does_not_match_c03(read):
    assert not matches(match_text("C03"), [read])


@pytest.mark.parametrize("read", ["E VII R", "EVIIR", "E.VII.R", "E VII", "VII R"])
def test_evii_r_never_matches_c04(read):
    assert not matches(match_text("C04"), [read])


def test_eviii_r_matches_c04_and_not_c02():
    assert matches(match_text("C04"), ["E VIII R"])
    assert not matches(match_text("C02"), ["E VIII R"])


def test_whole_words_only():
    assert not matches("GR", ["GRADE II LISTED"])
    assert not matches("GR", ["GREEN PARK"])
    assert not matches("MARX", ["MARXISM"])


def test_cypher_inside_longer_line():
    assert matches(match_text("C06"), ["ROYAL MAIL E II R"])


# Plaques and signs.


def test_karl_marx_needs_both_words():
    assert matches(match_text("P06"), ["KARL MARX", "1818-1883"])
    assert not matches(match_text("P06"), ["ELEANOR MARX", "1855-1898"])


def test_plus_terms_can_be_on_different_lines():
    lines = ["IN 1926 IN THIS HOUSE", "JOHN LOGIE BAIRD", "1888-1946", "FIRST DEMONSTRATED", "TELEVISION"]
    assert matches(match_text("P07"), lines)
    assert not matches(match_text("P07"), ["JOHN LOGIE BAIRD", "1888-1946", "LIVED HERE"])


def test_multi_word_phrase():
    assert matches(match_text("S06"), ["Dean Street W1", "City of Westminster"])
    assert matches(match_text("S06"), ["CITY OF", "WESTMINSTER"])
    assert not matches(match_text("S06"), ["CITY OF LONDON"])


def test_accents_and_case_are_ignored():
    assert matches("HANDEL", ["George Frideric Händel"])
    assert matches("HANDEL", ["handel"])


# Conflicting text on roundels.


def test_conflict_text_on_roundels():
    assert matches(CATALOGUE["T01"].conflict_text, ["London Overground"])
    assert matches(CATALOGUE["T01"].conflict_text, ["FRANK PICK"])
    assert matches(CATALOGUE["T01"].conflict_text, ["Elizabeth line"])
    assert not matches(CATALOGUE["T01"].conflict_text, ["UNDERGROUND"])
    assert not matches(CATALOGUE["T01"].conflict_text, ["SHEPHERD'S BUSH"])
    assert matches(CATALOGUE["T04"].conflict_text, ["UNDERGROUND"])
    assert not matches(CATALOGUE["T04"].conflict_text, ["BUS STOP"])


def test_empty_inputs():
    assert not matches("HENDRIX", [])
    assert not matches("", ["HENDRIX"])


# Numeral written after the letters, as larger models transcribe the monogram.


def test_numeral_last_matches_its_own_cypher():
    assert matches(match_text("C02"), ["E R VII"])
    assert matches(match_text("C04"), ["E R VIII"])
    assert matches(match_text("C05"), ["G R VI"])
    assert matches(match_text("C06"), ["E R II"])
    assert matches(match_text("C07"), ["C R III"])


@pytest.mark.parametrize("read", ["E R VII", "ER VII", "E.R.VII", "E VII R"])
def test_edward_vii_never_matches_c04_in_any_order(read):
    assert matches(match_text("C02"), [read])
    assert not matches(match_text("C04"), [read])


@pytest.mark.parametrize("read", ["E R", "ER", "E.R."])
def test_letters_without_a_numeral_match_no_cypher(read):
    for cypher in CATALOGUE.nested_items:
        assert not matches(cypher.match_text, [read]), cypher.id


def test_numeral_last_does_not_cross_cyphers():
    assert not matches(match_text("C06"), ["E R VII"])
    assert not matches(match_text("C02"), ["E R VIII"])
    # "G R VI" does contain the words G R; C03's conflict_text stops it (test_verification).
    assert matches(CATALOGUE["C03"].conflict_text, ["G R VI"])


# Pub Crawl: the pub's own name, as it appears on the sign.


@pytest.mark.parametrize(
    "item_id, lines",
    [
        ("B01", ["THE CHURCHILL ARMS"]),
        ("B01", ["CHURCHILL", "ARMS"]),
        ("B02", ["YE OLDE", "CHESHIRE CHEESE"]),
        ("B03", ["THE GEORGE"]),
        ("B03", ["George Inn"]),
        ("B04", ["THE BLACKFRIAR"]),
        ("B04", ["BLACK FRIAR"]),
        ("B05", ["LAMB & FLAG"]),
        ("B05", ["The Lamb and Flag"]),
        ("B06", ["YE OLDE MITRE"]),
        ("B07", ["SHAKESPEARE'S HEAD"]),
        ("B08", ["PROSPECT OF WHITBY"]),
        ("B09", ["THE MAYFLOWER"]),
        ("B10", ["THE SPANIARDS INN"]),
    ],
)
def test_pub_signs_match(item_id, lines):
    assert matches(match_text(item_id), lines)


@pytest.mark.parametrize(
    "item_id, lines",
    [
        ("B01", ["THE CHURCHILL"]),        # a different pub name
        ("B03", ["ST GEORGE'S TAVERN"]),  # George alone is not enough
        ("B05", ["THE LAMB"]),             # both words are needed
        ("B05", ["FLAG"]),
        ("B08", ["THE PROSPECT"]),
        ("B08", ["WHITBY"]),
        ("B06", ["MITRED"]),               # whole words only
        ("B07", ["SHAKESPEAREAN"]),
        ("B10", ["SPANIARD"]),
    ],
)
def test_other_pub_names_do_not_match(item_id, lines):
    assert not matches(match_text(item_id), lines)
