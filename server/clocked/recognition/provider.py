"""The one interface every vision model provider implements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from clocked.catalogue import Catalogue
from clocked.recognition.schema import ModelAnswer, Usage


class ProviderError(RuntimeError):
    """The provider could not produce an answer. The app shows a Retry button."""


@dataclass
class BlindRead:
    """Text read with no list of collectibles, so the model has nothing to expect."""

    lines: list[str]
    usage: Usage
    raw: dict


@dataclass
class ProviderResult:
    answer: ModelAnswer
    usage: Usage
    raw: dict


class VisionProvider(Protocol):
    name: str
    model: str

    def recognise(
        self, image: bytes, media_type: str, catalogue: Catalogue, filename: str | None = None
    ) -> ProviderResult:
        """Return a structured candidate answer for one photo.

        The photo is the only input about the player: location is never sent.
        `filename` is used only by the fake provider in tests.
        """
        ...

    def read_text(self, image: bytes, media_type: str, filename: str | None = None) -> BlindRead:
        """Transcribe readable text in the photo without any list of collectibles."""
        ...
