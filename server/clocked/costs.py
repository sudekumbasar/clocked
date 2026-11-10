"""A ledger of model costs, so the running total against the budget is always known."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from clocked.recognition.schema import Usage

FIELDS = ["time_utc", "provider", "model", "input_tokens", "output_tokens", "cost_usd", "source"]


class BudgetExceeded(RuntimeError):
    """A real model call would go past the agreed budget stop."""


class CostLedger:
    def __init__(self, path: Path):
        self.path = Path(path)

    def record(self, usage: Usage, source: str) -> None:
        if usage.provider == "fake":
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        new_file = not self.path.exists()
        with open(self.path, "a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            if new_file:
                writer.writeheader()
            writer.writerow(
                {
                    "time_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "provider": usage.provider,
                    "model": usage.model,
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "cost_usd": f"{usage.cost_usd:.6f}",
                    "source": source,
                }
            )

    def rows(self) -> list[dict[str, str]]:
        if not self.path.exists():
            return []
        with open(self.path, newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))

    def total_usd(self) -> float:
        return sum(float(row["cost_usd"]) for row in self.rows())

    def average_usd(self, model: str) -> float | None:
        costs = [float(row["cost_usd"]) for row in self.rows() if row["model"].startswith(model)]
        return sum(costs) / len(costs) if costs else None
