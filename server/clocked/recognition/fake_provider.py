"""A provider that returns scripted answers, for tests and for demos without an API key.

Answers are looked up by the photo's file name, then by the SHA-256 of its bytes.
Anything not scripted gets an empty answer ("none of these") and reads no text.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from clocked.catalogue import Catalogue
from clocked.recognition.provider import BlindRead, ProviderResult
from clocked.recognition.schema import ModelAnswer, Usage


class FakeProvider:
    name = "fake"
    model = "fake"

    def __init__(
        self,
        answers: dict[str, ModelAnswer | dict] | None = None,
        blind_reads: dict[str, list[str]] | None = None,
    ):
        self.blind_reads = blind_reads or {}
        self.answers = {
            key: value if isinstance(value, ModelAnswer) else ModelAnswer.model_validate(value)
            for key, value in (answers or {}).items()
        }
        self.calls: list[dict] = []

    @classmethod
    def from_file(cls, path: Path) -> "FakeProvider":
        """Answers keyed by file name; an entry may also carry the blind reading as "blind_lines"."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        blind = {key: value.pop("blind_lines") for key, value in data.items() if "blind_lines" in value}
        return cls(data, blind)

    def recognise(
        self, image: bytes, media_type: str, catalogue: Catalogue, filename: str | None = None
    ) -> ProviderResult:
        self.calls.append({"image": image, "media_type": media_type, "filename": filename})
        digest = hashlib.sha256(image).hexdigest()
        answer = self.answers.get(filename or "") or self.answers.get(digest) or ModelAnswer()
        return ProviderResult(
            answer=answer,
            usage=Usage(provider=self.name, model=self.model),
            raw={"fake": True, "answer": answer.model_dump()},
        )

    def read_text(self, image: bytes, media_type: str, filename: str | None = None) -> BlindRead:
        lines = self.blind_reads.get(filename or "", [])
        return BlindRead(lines=lines, usage=Usage(provider=self.name, model=self.model),
                         raw={"fake": True, "lines": lines})
