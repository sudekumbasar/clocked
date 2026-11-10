"""Text shown to the player for each outcome (PRODUCT.md, "Outcomes" and "When things go wrong")."""

CLOCKED_IT = "CLOCKED IT!"
MIGHT_BE = "I think this might be: {name}. Take a closer photo to confirm."
COULD_NOT_IDENTIFY = "Couldn't identify this one. Try getting closer or capturing any text or signs."
NEED_LOCATION = "We recognised this, but need your location to verify the discovery."
LOCATION_IMPRECISE = (
    "Your location isn't precise enough to verify this yet. Wait a moment and try again."
)
NOT_NEAR = "This looks like {name}, but you don't seem to be near it."
PICTURE = "This looks like a picture of {name}, not the real thing. Take a photo of the real one."

_BY_REASON = {
    "passed": CLOCKED_IT,
    "passed_text_and_location": CLOCKED_IT,
    "medium_confidence": MIGHT_BE,
    "text_missing": MIGHT_BE,
    "blind_text_missing": MIGHT_BE,
    "text_conflict": MIGHT_BE,
    "location_missing": NEED_LOCATION,
    "location_imprecise": LOCATION_IMPRECISE,
    "out_of_radius_named": NOT_NEAR,
    "photo_of_picture": PICTURE,
}


def for_check(reason_code: str, name: str) -> str:
    return _BY_REASON.get(reason_code, COULD_NOT_IDENTIFY).format(name=name)
