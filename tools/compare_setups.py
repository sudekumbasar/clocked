"""Compare recognition setups on the labelled test set.

Every photo gets four calls, each saved in a cache so a call is never paid for
twice: main answer and blind reading, each on Haiku 4.5 and on Sonnet 5.5. The
setups are then scored from those calls, with the same verification rules:

  A  Haiku                 Haiku answers, Haiku reads
  B  Haiku + Sonnet reads  Haiku answers, Sonnet reads
  B2 B, Sonnet for boxes   as B, but when Haiku proposes a post box, Sonnet answers too
  C  Sonnet                Sonnet answers, Sonnet reads

Cost and time are reported two ways: blind reading only when needed, after the
main answer ("sequential"), or always, at the same time ("parallel": the slower
of the two calls).

Run from the App folder:
  server/.venv/bin/python tools/compare_setups.py [--estimate]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "server"))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from clocked.catalogue import Catalogue, load_catalogue  # noqa: E402
from clocked.config import Settings  # noqa: E402
from clocked.costs import CostLedger  # noqa: E402
from clocked.images import prepare  # noqa: E402
from clocked.recognition.anthropic_provider import AnthropicProvider  # noqa: E402
from clocked.recognition.prompt import prompt_version  # noqa: E402
from clocked.recognition.schema import ModelAnswer  # noqa: E402
from clocked.verification import Thresholds, needs_blind_read, verify  # noqa: E402
from score_photos import Label, load_labels  # noqa: E402

HAIKU, SONNET = "claude-haiku-4-5", "claude-sonnet-5-5"
MODELS = (HAIKU, SONNET)
# Per photo, both calls on both models, from the earlier trial runs.
ESTIMATE_PER_PHOTO = {HAIKU: 0.0063, SONNET: 0.0163}
CACHE = REPO_ROOT / "testset" / "runs" / "compare_cache.jsonl"


@dataclass
class Call:
    answer: ModelAnswer | None
    lines: list[str] | None
    cost: float
    seconds: float


def cache_key(digest: str, model: str, kind: str, version: str) -> str:
    return f"{digest}:{model}:{kind}:{version}"


def load_cache() -> dict[str, dict]:
    if not CACHE.exists():
        return {}
    return {r["key"]: r for r in map(json.loads, CACHE.read_text(encoding="utf-8").splitlines())}


def collect(labels: list[Label], catalogue: Catalogue, ledger: CostLedger) -> dict:
    """Make (or reuse) the four calls per photo. Returns {file: {(model, kind): Call}}."""
    cache = load_cache()
    version = prompt_version(catalogue)
    providers = {m: AnthropicProvider(m) for m in MODELS}
    calls: dict[str, dict] = {}
    with open(CACHE, "a", encoding="utf-8") as out:
        for number, label in enumerate(labels, 1):
            data = (REPO_ROOT / "testset" / "photos" / label.file).read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            image, media_type = prepare(data)
            calls[label.file] = {}
            for model in MODELS:
                for kind in ("main", "blind"):
                    key = cache_key(digest, model, kind, version)
                    if key not in cache:
                        print(f"  [{number}/{len(labels)}] {label.file} {model} {kind}", file=sys.stderr)
                        started = time.perf_counter()
                        if kind == "main":
                            result = providers[model].recognise(image, media_type, catalogue)
                            payload = {"answer": result.answer.model_dump(mode="json")}
                        else:
                            result = providers[model].read_text(image, media_type)
                            payload = {"lines": result.lines}
                        seconds = time.perf_counter() - started
                        ledger.record(result.usage, source="compare-setups")
                        cache[key] = {"key": key, "file": label.file, "model": model, "kind": kind,
                                      "cost": result.usage.cost_usd, "seconds": seconds, **payload}
                        out.write(json.dumps(cache[key]) + "\n")
                        out.flush()
                    record = cache[key]
                    calls[label.file][(model, kind)] = Call(
                        answer=ModelAnswer.model_validate(record["answer"]) if kind == "main" else None,
                        lines=record.get("lines"),
                        cost=record["cost"],
                        seconds=record["seconds"],
                    )
    return calls


@dataclass
class Outcome:
    outcome: str
    item_id: str | None
    cypher_id: str | None
    reason: str
    cost_seq: float
    cost_par: float
    secs_seq: float
    secs_par: float


def run_setup(name: str, c: dict, label: Label, catalogue: Catalogue, thresholds: Thresholds) -> Outcome:
    haiku_main, sonnet_main = c[(HAIKU, "main")], c[(SONNET, "main")]
    reader_model = HAIKU if name == "A" else SONNET
    main_model = SONNET if name == "C" else HAIKU
    main = c[(main_model, "main")]
    blind = c[(reader_model, "blind")]
    extra_cost, extra_secs = 0.0, 0.0
    if name == "B2":
        parents = {item.parent_id for item in catalogue.nested_items}
        if any(cand.candidate_id in parents for cand in haiku_main.answer.candidates):
            # Haiku saw a post box: Sonnet answers as well, after Haiku.
            main = sonnet_main
            extra_cost, extra_secs = haiku_main.cost, haiku_main.seconds

    needed = needs_blind_read(main.answer, catalogue)
    result = verify(main.answer, catalogue, label.location, thresholds, blind.lines if needed else None)
    return Outcome(
        outcome=result.outcome.value,
        item_id=result.item_id,
        cypher_id=result.cypher_id,
        reason=result.reason_code,
        cost_seq=extra_cost + main.cost + (blind.cost if needed else 0.0),
        cost_par=extra_cost + main.cost + blind.cost,
        secs_seq=extra_secs + main.seconds + (blind.seconds if needed else 0.0),
        secs_par=extra_secs + max(main.seconds, blind.seconds),
    )


SETUPS = {
    "A": "Haiku",
    "B": "Haiku + Sonnet reads",
    "B2": "Haiku + Sonnet reads, Sonnet for post boxes",
    "C": "Sonnet",
}


def report(labels, calls, catalogue, thresholds) -> str:
    out = [f"# Setup comparison {datetime.now():%Y-%m-%d %H:%M}", "",
           f"Photos: {len(labels)} ({sum(not l.is_negative for l in labels)} positives, "
           f"{sum(l.is_negative for l in labels)} negatives). Thresholds: high {thresholds.high}, "
           f"medium {thresholds.medium}.", ""]
    rows, details = [], {}
    for key, title in SETUPS.items():
        results = [(label, run_setup(key, calls[label.file], label, catalogue, thresholds)) for label in labels]
        details[key] = results
        wrong = [(l, r) for l, r in results if r.outcome == "AWARD" and r.item_id not in l.accepted_ids]
        wrong_cy = [(l, r) for l, r in results if r.cypher_id and r.cypher_id != l.expected_cypher]
        clear = [(l, r) for l, r in results if not l.is_negative and l.clear
                 and catalogue[l.expected_id].rarity == "common"]
        first = sum(r.outcome == "AWARD" and r.item_id in l.accepted_ids for l, r in clear)
        pos = [(l, r) for l, r in results if not l.is_negative]
        pos_award = sum(r.outcome == "AWARD" and r.item_id in l.accepted_ids for l, r in pos)
        n = len(results)
        rows.append(
            f"| {key} {title} | **{len(wrong) + len(wrong_cy)}** | {first}/{len(clear)} "
            f"({100 * first / max(len(clear), 1):.0f}%) | {pos_award}/{len(pos)} | "
            f"${sum(r.cost_seq for _, r in results) / n:.4f} / ${sum(r.cost_par for _, r in results) / n:.4f} | "
            f"{statistics.mean(r.secs_seq for _, r in results):.1f} / {statistics.mean(r.secs_par for _, r in results):.1f} s |"
        )
    out += ["| Setup | Wrong awards | Clear common items, first time | All positives awarded | "
            "Cost per photo (sequential / parallel) | Mean time (sequential / parallel) |",
            "|---|---|---|---|---|---|", *rows, ""]

    out += ["## Wrong awards", ""]
    any_wrong = False
    for key, results in details.items():
        for l, r in results:
            if (r.outcome == "AWARD" and r.item_id not in l.accepted_ids) or (
                    r.cypher_id and r.cypher_id != l.expected_cypher):
                any_wrong = True
                out.append(f"- {key}: {l.file} awarded {r.item_id} {r.cypher_id or ''}, "
                           f"expected {l.expected_id or 'nothing'} {l.expected_cypher}")
    if not any_wrong:
        out.append("None in any setup.")
    out.append("")

    out += ["## Royal cyphers", "",
            "| Setup | Correct | Wrong | Missed (box awarded, no cypher) | Box not awarded |",
            "|---|---|---|---|---|"]
    cy_labels = [l for l in labels if l.expected_cypher]
    for key, results in details.items():
        res = {l.file: r for l, r in results}
        correct = sum(res[l.file].cypher_id == l.expected_cypher for l in cy_labels)
        wrong = sum(1 for l, r in results if r.cypher_id and r.cypher_id != l.expected_cypher)
        missed = sum(res[l.file].item_id == "S02" and res[l.file].cypher_id is None for l in cy_labels)
        no_box = sum(res[l.file].item_id != "S02" for l in cy_labels)
        out.append(f"| {key} {SETUPS[key]} | {correct}/{len(cy_labels)} | {wrong} | {missed} | {no_box} |")
    out.append("")
    clear = [l for l in cy_labels if l.cypher_clear]
    out += [f"Clear close-ups only ({len(clear)} photos):", "",
            "| Setup | Correct | Wrong | Rule: no wrong cypher and at least half correct |", "|---|---|---|---|"]
    for key, results in details.items():
        res = {l.file: r for l, r in results}
        correct = sum(res[l.file].cypher_id == l.expected_cypher for l in clear)
        wrong = sum(1 for l, r in results if r.cypher_id and r.cypher_id != l.expected_cypher)
        verdict = "keep" if wrong == 0 and correct * 2 >= len(clear) else "drop"
        out.append(f"| {key} {SETUPS[key]} | {correct}/{len(clear)} | {wrong} | {verdict} |")
    out += ["", "| Cypher photo | Expected | Clear | " + " | ".join(SETUPS) + " |", "|---|---|---|" + "---|" * len(SETUPS)]
    for l in [l for l in labels if l.expected_cypher or l.file.startswith("s02_") or "cypher" in l.note.lower()]:
        cells = [f"{details[k][labels.index(l)][1].item_id or '-'}+{details[k][labels.index(l)][1].cypher_id or '-'}" for k in SETUPS]
        out.append(f"| {l.file} | {l.expected_cypher or '-'} | {'y' if l.cypher_clear else ''} | " + " | ".join(cells) + " |")
    out.append("")

    out += ["## Per photo", "", "| Photo | Expected | " + " | ".join(SETUPS) + " |",
            "|---|---|" + "---|" * len(SETUPS)]
    for i, label in enumerate(labels):
        cells = []
        for key in SETUPS:
            r = details[key][i][1]
            cells.append(f"{r.outcome} {r.item_id or ''}{('+' + r.cypher_id) if r.cypher_id else ''} ({r.reason})")
        exp = (label.expected_id or "negative") + (f"+{label.expected_cypher}" if label.expected_cypher else "")
        out.append(f"| {label.file} | {exp} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--estimate", action="store_true", help="print the cost estimate and stop")
    parser.add_argument("--yes-over-budget", action="store_true")
    args = parser.parse_args()

    settings = Settings.from_env()
    catalogue = load_catalogue(settings.csv_path)
    thresholds = Thresholds.load()
    ledger = CostLedger(settings.cost_ledger)
    labels = load_labels(REPO_ROOT / "testset" / "labels.csv", catalogue)

    cache = load_cache()
    version = prompt_version(catalogue)
    todo = 0
    for label in labels:
        digest = hashlib.sha256((REPO_ROOT / "testset" / "photos" / label.file).read_bytes()).hexdigest()
        if any(cache_key(digest, m, k, version) not in cache for m in MODELS for k in ("main", "blind")):
            todo += 1
    estimate = todo * sum(ESTIMATE_PER_PHOTO.values())
    spent = ledger.total_usd()
    print(f"{todo} of {len(labels)} photos need calls. Estimate ${estimate:.2f}; "
          f"spent so far ${spent:.2f}; after: about ${spent + estimate:.2f}.", file=sys.stderr)
    if args.estimate:
        return 0
    if spent + estimate > settings.budget_stop_usd and not args.yes_over_budget:
        sys.exit(f"This could take the total past ${settings.budget_stop_usd:.2f}. Ask the project owner first.")

    calls = collect(labels, catalogue, ledger)
    text = report(labels, calls, catalogue, thresholds)
    path = REPO_ROOT / "testset" / "runs" / f"compare_{datetime.now():%Y%m%d-%H%M%S}.md"
    path.write_text(text + "\n", encoding="utf-8")
    print(text)
    print(f"\nSaved to {path.relative_to(REPO_ROOT)}. Running total: ${ledger.total_usd():.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
