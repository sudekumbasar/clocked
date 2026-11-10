"""Server settings, read from the environment and the repository's .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from clocked.catalogue import DEFAULT_CSV, REPO_ROOT

ENV_FILE = REPO_ROOT / ".env"


def load_env_file(path: Path = ENV_FILE) -> None:
    """Load KEY=VALUE lines into the environment without overriding what is already set."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if value and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class Settings:
    provider: str = "anthropic"
    model: str = "claude-sonnet-5-5"
    # Model for the blind reading; None means the same as `model`.
    reader_model: str | None = None
    # "sequential": blind reading only when needed; "parallel": always, alongside.
    blind_mode: str = "sequential"
    csv_path: Path = DEFAULT_CSV
    fake_answers: Path | None = None
    cost_ledger: Path = REPO_ROOT / "testset" / "runs" / "cost_ledger.csv"
    budget_stop_usd: float = 8.0
    # Sets in the CSV that are not in this version. Their rows stay in the CSV.
    # Royal Cyphers: moved to the next version after step 1. Retired: items left
    # out in revision 5 (PRODUCT.md).
    disabled_sets: tuple[str, ...] = ("royal-cyphers", "retired")
    # Recognitions allowed per player (by address), so a public address cannot spend the budget.
    rate_per_minute: int = 10
    rate_per_day: int = 150
    # Photos larger than this are refused before anything else happens.
    max_upload_bytes: int = 15 * 1024 * 1024
    # Field test: one log line per recognition (outcome, confidence, distance; never the photo
    # or coordinates), for tuning thresholds. Cloud logs delete themselves after 30 days.
    field_log: bool = False
    # Development mode adds nothing yet. It is the only switch that may ever
    # enable development endpoints, and the public server never sets it.
    dev_mode: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        load_env_file()
        env = os.environ
        fake = env.get("CLOCKED_FAKE_ANSWERS")
        return cls(
            provider=env.get("CLOCKED_PROVIDER", cls.provider),
            model=env.get("CLOCKED_MODEL", cls.model),
            reader_model=env.get("CLOCKED_READER_MODEL") or None,
            blind_mode=env.get("CLOCKED_BLIND_MODE", cls.blind_mode),
            csv_path=Path(env.get("CLOCKED_CSV", str(cls.csv_path))),
            fake_answers=Path(fake) if fake else None,
            cost_ledger=Path(env.get("CLOCKED_COST_LEDGER", str(cls.cost_ledger))),
            budget_stop_usd=float(env.get("CLOCKED_BUDGET_STOP_USD", cls.budget_stop_usd)),
            rate_per_minute=int(env.get("CLOCKED_RATE_PER_MINUTE", cls.rate_per_minute)),
            rate_per_day=int(env.get("CLOCKED_RATE_PER_DAY", cls.rate_per_day)),
            max_upload_bytes=int(env.get("CLOCKED_MAX_UPLOAD_BYTES", cls.max_upload_bytes)),
            field_log=env.get("CLOCKED_FIELD_LOG") == "1",
            dev_mode=env.get("CLOCKED_DEV_MODE") == "1",
        )
