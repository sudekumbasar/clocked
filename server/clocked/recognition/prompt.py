"""The prompt and output schema sent to the vision model, built from the catalogue.

Only id, name, category and model_hint are sent. `notes` are for us and are
never sent, and nothing about the player (such as location) is ever sent.
"""

from __future__ import annotations

import hashlib
import json

from clocked.catalogue import Catalogue
from clocked.recognition.schema import MAX_CANDIDATES

INSTRUCTIONS = f"""\
You identify London collectibles in a photo for a collection game. You do not decide \
whether anything is awarded; you only report what you see.

You are given a list of collectibles. Look at the photo and answer only in the JSON \
format requested.

Rules:
1. Choose only from the list. If nothing in the photo clearly is an item on the list, \
return an empty candidates list. "None of these" is a common and correct answer.
2. Give at most {MAX_CANDIDATES} candidates, most certain first. Give a second candidate \
only when a different item from the list is also clearly visible in the photo. Never \
give the same item twice.
3. confidence is how sure you are that the object is that item, from 0 to 1. Be strict: \
if the photo is blurred, far away or partly hidden, or the object only looks similar, \
give a low confidence.
4. object_text: the text you can actually read on that object itself in this photo, one \
entry per line of text, copied exactly. Never write text you expect to be there because \
of the list, an item's name or what such objects usually say. If text is too small, \
blurred or stylised to read letter by letter, leave it out, even if you think you know \
what it says.
5. other_text: any other text you can actually read elsewhere in the photo.
6. If you can read a person's name on a plaque and that person is on the list, give that \
plaque as a candidate.
7. cypher_id: only when a candidate is a post box and you can read every letter and \
Roman numeral of the royal cypher on that post box. Write exactly the letters and \
numerals you can see into that post box's object_text, separated by spaces. If you \
cannot make out every letter and numeral, cypher_id is null and cypher_confidence is 0.
8. photo_of_picture: true when the collectible is shown as a picture of it rather than \
being the real thing in front of the camera: on a phone, computer or TV screen, a poster, \
a billboard, a printed photo, a postcard, a book or a magazine, or as a model, toy or \
souvenir. A real object that happens to carry an advert or a picture (a real bus with an \
advert on its side) is still the real thing. If unsure, say true.
9. reason: one short sentence describing what you see.
"""


def _item_line(item) -> str:
    return f"- {item.id} | {item.name} | {item.category} | {item.model_hint}"


def system_prompt(catalogue: Catalogue) -> str:
    lines = [INSTRUCTIONS, "Collectibles (choose candidate_id from these):"]
    lines += [_item_line(item) for item in catalogue.main_items]
    if catalogue.nested_items:
        lines += ["", "Royal cyphers (only for cypher_id, never as a candidate):"]
        lines += [_item_line(item) for item in catalogue.nested_items]
    return "\n".join(lines)


USER_TEXT = "Identify this photo."


def output_schema(catalogue: Catalogue) -> dict:
    """JSON schema for the answer. Enums stop the model naming items not in the CSV."""
    main_ids = [item.id for item in catalogue.main_items]
    cypher_ids = [item.id for item in catalogue.nested_items]
    text_list = {"type": "array", "items": {"type": "string"}}
    cypher = (
        {"anyOf": [{"type": "string", "enum": cypher_ids}, {"type": "null"}]}
        if cypher_ids
        else {"type": "null"}
    )
    return {
        "type": "object",
        "properties": {
            "candidates": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "candidate_id": {"type": "string", "enum": main_ids},
                        "confidence": {"type": "number"},
                        "object_text": text_list,
                    },
                    "required": ["candidate_id", "confidence", "object_text"],
                    "additionalProperties": False,
                },
            },
            "cypher_id": cypher,
            "cypher_confidence": {"type": "number"},
            "other_text": text_list,
            "photo_of_picture": {"type": "boolean"},
            "reason": {"type": "string"},
        },
        "required": ["candidates", "cypher_id", "cypher_confidence", "other_text", "photo_of_picture", "reason"],
        "additionalProperties": False,
    }


def prompt_version(catalogue: Catalogue) -> str:
    """Short hash of everything sent besides the photo, for caching saved answers."""
    payload = json.dumps(
        [system_prompt(catalogue), USER_TEXT, output_schema(catalogue)], sort_keys=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


BLIND_READ_INSTRUCTIONS = """\
Transcribe the text that is printed, painted, cast or engraved in this photo.

Rules:
1. Copy only letters and numbers you can actually see, exactly as they appear, one entry \
per line of text.
2. Do not guess, do not complete partial words, and do not add text you would expect to \
be there.
3. If letters are joined into a decorative monogram, write each letter and Roman numeral \
you can make out, separated by spaces. If you cannot make out all of them, do not write \
that monogram at all.
4. If you cannot read any text, set readable to false and return no lines.
"""

BLIND_READ_USER_TEXT = "Transcribe the readable text in this photo."

BLIND_READ_SCHEMA = {
    "type": "object",
    "properties": {
        "readable": {"type": "boolean"},
        "lines": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["readable", "lines"],
    "additionalProperties": False,
}
