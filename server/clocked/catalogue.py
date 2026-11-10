"""Load and validate the collectibles CSV.

Everything about a collectible comes from the CSV. The loader refuses data that
would make the verification rules ambiguous, so problems surface at startup
rather than as a wrong award.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = REPO_ROOT / "data" / "london_collection_v4.csv"

KINDS = {"type", "place"}
RARITIES = {"common", "rare", "legendary"}
SIGNALS = {"vision", "text", "location"}


class CatalogueError(ValueError):
    """The CSV breaks a rule the verification step relies on."""


@dataclass(frozen=True)
class Item:
    id: str
    set: str
    name: str
    category: str
    kind: str
    rarity: str
    signals: frozenset[str]
    access: str
    location: str
    lat: float | None
    lng: float | None
    radius_m: float | None
    clue: str
    fact: str
    source_url: str
    notes: str
    match_text: str
    model_hint: str
    conflict_text: str
    parent_id: str

    @property
    def needs_text(self) -> bool:
        return "text" in self.signals

    @property
    def needs_location(self) -> bool:
        return "location" in self.signals

    @property
    def is_place(self) -> bool:
        return self.kind == "place"

    @property
    def is_nested(self) -> bool:
        return bool(self.parent_id)


@dataclass(frozen=True)
class Catalogue:
    items: tuple[Item, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "_by_id", {item.id: item for item in self.items})

    def get(self, item_id: str) -> Item | None:
        return self._by_id.get(item_id)  # type: ignore[attr-defined]

    def __getitem__(self, item_id: str) -> Item:
        return self._by_id[item_id]  # type: ignore[attr-defined]

    @property
    def main_items(self) -> list[Item]:
        """Items the model can name as a candidate."""
        return [item for item in self.items if not item.is_nested]

    @property
    def nested_items(self) -> list[Item]:
        """Items only awarded alongside their parent (the royal cyphers)."""
        return [item for item in self.items if item.is_nested]


def _optional_float(row: dict[str, str], column: str, item_id: str) -> float | None:
    value = row[column].strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        raise CatalogueError(f"{item_id}: {column} is not a number: {value!r}") from None


def _parse_signals(value: str, item_id: str) -> frozenset[str]:
    parts = [part.strip() for part in value.split("+")]
    signals = frozenset(parts)
    if "vision" not in signals or not signals <= SIGNALS or len(parts) != len(signals):
        raise CatalogueError(f"{item_id}: verification {value!r} is not valid")
    return signals


def _parse_row(row: dict[str, str]) -> Item:
    item_id = row["id"].strip()
    if not item_id:
        raise CatalogueError("an item has no id")
    return Item(
        id=item_id,
        set=row["set"].strip(),
        name=row["name"].strip(),
        category=row["category"].strip(),
        kind=row["kind"].strip(),
        rarity=row["rarity"].strip(),
        signals=_parse_signals(row["verification"], item_id),
        access=row["access"].strip(),
        location=row["location"].strip(),
        lat=_optional_float(row, "lat", item_id),
        lng=_optional_float(row, "lng", item_id),
        radius_m=_optional_float(row, "verification_radius_m", item_id),
        clue=row["clue"].strip(),
        fact=row["fact"].strip(),
        source_url=row["source_url"].strip(),
        notes=row["notes"].strip(),
        match_text=row["match_text"].strip(),
        model_hint=row["model_hint"].strip(),
        conflict_text=row["conflict_text"].strip(),
        parent_id=row["parent_id"].strip(),
    )


def _validate_item(item: Item) -> None:
    def fail(message: str) -> None:
        raise CatalogueError(f"{item.id}: {message}")

    if item.kind not in KINDS:
        fail(f"kind {item.kind!r} is not one of {sorted(KINDS)}")
    if item.rarity not in RARITIES:
        fail(f"rarity {item.rarity!r} is not one of {sorted(RARITIES)}")
    for column in ("name", "category", "fact", "model_hint"):
        if not getattr(item, column):
            fail(f"{column} is empty")

    if item.needs_text != bool(item.match_text):
        fail("match_text must be filled exactly when verification includes text")

    if item.needs_location != (item.radius_m is not None):
        fail("verification_radius_m must be filled exactly when verification includes location")
    if item.radius_m is not None and item.radius_m <= 0:
        fail("verification_radius_m must be positive")

    if item.is_place:
        if item.lat is None or item.lng is None:
            fail("place items need lat and lng")
    else:
        if item.lat is not None or item.lng is not None or item.radius_m is not None or item.clue:
            fail("type items must leave lat, lng, verification_radius_m and clue empty")
        if item.needs_location:
            fail("type items cannot be verified by location")


def load_catalogue(path: Path = DEFAULT_CSV, disabled_sets: tuple[str, ...] = ()) -> Catalogue:
    """Load every item, then leave out the sets that are switched off (their data stays)."""
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {
            "id", "set", "name", "category", "kind", "rarity", "verification", "access",
            "location", "lat", "lng", "verification_radius_m", "clue", "fact", "source_url",
            "notes", "match_text", "model_hint", "conflict_text", "parent_id",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise CatalogueError(f"CSV is missing columns: {sorted(missing)}")
        items = [_parse_row(row) for row in reader]

    seen: set[str] = set()
    for item in items:
        if item.id in seen:
            raise CatalogueError(f"{item.id}: duplicate id")
        seen.add(item.id)
        _validate_item(item)

    by_id = {item.id: item for item in items}
    for item in items:
        if item.parent_id:
            parent = by_id.get(item.parent_id)
            if parent is None:
                raise CatalogueError(f"{item.id}: parent_id {item.parent_id!r} does not exist")
            if parent.parent_id:
                raise CatalogueError(f"{item.id}: parent {parent.id} is itself nested")
            if item.needs_location:
                raise CatalogueError(f"{item.id}: nested items cannot be verified by location")

    return Catalogue(items=tuple(item for item in items if item.set not in disabled_sets))
