from clocked.catalogue import load_catalogue
from clocked.recognition.prompt import output_schema, prompt_version, system_prompt

CATALOGUE = load_catalogue()


def test_candidate_enum_is_main_items_and_cypher_enum_is_nested_items():
    schema = output_schema(CATALOGUE)
    candidate_enum = schema["properties"]["candidates"]["items"]["properties"]["candidate_id"]["enum"]
    cypher_enum = schema["properties"]["cypher_id"]["anyOf"][0]["enum"]
    assert candidate_enum == [item.id for item in CATALOGUE.main_items]
    assert cypher_enum == [item.id for item in CATALOGUE.nested_items]
    assert not set(candidate_enum) & set(cypher_enum)


def test_prompt_has_every_item_and_hint_but_no_notes_or_facts():
    prompt = system_prompt(CATALOGUE)
    for item in CATALOGUE.items:
        assert item.id in prompt
        assert item.model_hint in prompt
        if item.notes:
            assert item.notes not in prompt
        assert item.fact not in prompt


def test_prompt_says_none_of_these_is_valid():
    assert "None of these" in system_prompt(CATALOGUE)


def test_prompt_version_is_stable():
    assert prompt_version(CATALOGUE) == prompt_version(CATALOGUE)
