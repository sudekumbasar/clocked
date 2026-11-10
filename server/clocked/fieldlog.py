"""One log line per recognition during the field test (PRODUCT.md, step 5).

Written as JSON to standard output, which Cloud Run keeps as a structured log for
30 days. It holds what tuning the thresholds needs: the model's answer, the outcome,
the confidence and how far the player was from the item. It never holds the photo or
the player's coordinates.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import TextIO

from clocked.recognition.schema import Location, ModelAnswer, Result, Usage


def field_record(answer: ModelAnswer, blind_lines: list[str] | None, result: Result,
                 location: Location | None, usage: Usage) -> dict:
    distances = {check.candidate_id: check.distance_m for check in result.checks if check.distance_m is not None}
    top = answer.candidates[0] if answer.candidates else None
    return {
        "event": "recognition",
        "time_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "outcome": result.outcome.value,
        "item_id": result.item_id,
        "reason_code": result.reason_code,
        "top_candidate": top.candidate_id if top else None,
        "top_confidence": top.confidence if top else None,
        "distance_m": {k: round(v) for k, v in distances.items()},
        "had_location": location is not None,
        "accuracy_m": round(location.accuracy_m) if location else None,
        "model": usage.model,
        "cost_usd": round(usage.cost_usd, 6),
        "answer": answer.model_dump(mode="json"),
        "blind_lines": blind_lines,
    }


def write_field_record(record: dict, out: TextIO | None = None) -> None:
    # Cloud Logging reads "severity" and "message" from a JSON line.
    out = out or sys.stdout  # looked up on each call, so a replaced stdout is honoured
    out.write(json.dumps({"severity": "INFO", "message": "recognition", **record}) + "\n")
    out.flush()
