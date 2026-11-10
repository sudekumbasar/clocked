"""One recognition: the main answer plus, when an award could depend on text, a blind reading.

The blind reading can come from a different provider or model than the main answer.
In "sequential" mode it runs only when needed, after the main answer. In "parallel"
mode it always runs, at the same time as the main answer.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from clocked.catalogue import Catalogue
from clocked.recognition.provider import BlindRead, ProviderResult, VisionProvider
from clocked.recognition.schema import ModelAnswer, Usage
from clocked.verification import needs_blind_read

MODES = ("sequential", "parallel")


@dataclass
class Recognition:
    answer: ModelAnswer
    blind_lines: list[str] | None
    usages: list[Usage] = field(default_factory=list)
    seconds: float = 0.0


class Recogniser:
    def __init__(self, main: VisionProvider, reader: VisionProvider, mode: str = "sequential"):
        if mode not in MODES:
            raise ValueError(f"unknown blind reading mode {mode!r}")
        self.main, self.reader, self.mode = main, reader, mode

    def run(
        self, image: bytes, media_type: str, catalogue: Catalogue, filename: str | None = None
    ) -> Recognition:
        started = time.perf_counter()
        blind: BlindRead | None
        if self.mode == "parallel":
            with ThreadPoolExecutor(max_workers=2) as pool:
                main_future = pool.submit(self.main.recognise, image, media_type, catalogue, filename)
                blind_future = pool.submit(self.reader.read_text, image, media_type, filename)
                main: ProviderResult = main_future.result()
                blind = blind_future.result()
        else:
            main = self.main.recognise(image, media_type, catalogue, filename)
            needed = needs_blind_read(main.answer, catalogue)
            blind = self.reader.read_text(image, media_type, filename) if needed else None

        usages = [main.usage] + ([blind.usage] if blind else [])
        return Recognition(
            answer=main.answer,
            blind_lines=blind.lines if blind else None,
            usages=usages,
            seconds=time.perf_counter() - started,
        )
