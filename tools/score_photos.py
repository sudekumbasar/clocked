"""Score a folder of photos through the recognition endpoint (PRODUCT.md, "Testing without being there").

Reports awards, retries and rejects, lists every wrong award first, and logs the
model cost of the run. Exits with code 1 if there is any wrong award.

Examples (run from the App folder):
  server/.venv/bin/python tools/score_photos.py --provider fake --fake-answers testset/fake_answers.json
  server/.venv/bin/python tools/score_photos.py --provider anthropic --model claude-haiku-4-5
  server/.venv/bin/python tools/score_photos.py --rules-only testset/runs/<run folder>
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "server"))

from clocked.catalogue import Catalogue, load_catalogue  # noqa: E402
from clocked.config import Settings  # noqa: E402
from clocked.costs import CostLedger  # noqa: E402
from clocked.recognition.prompt import prompt_version  # noqa: E402
from clocked.recognition.schema import Location, ModelAnswer, Usage  # noqa: E402
from clocked.verification import Thresholds, verify  # noqa: E402

PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
LABEL_FIELDS = [
    "file", "expected_id", "also_ok", "expected_cypher", "lat", "lng", "accuracy_m",
    "clear", "source", "licence", "note", "cypher_clear",
]
DEFAULT_ACCURACY_M = 10.0
BUDGET_TOTAL_USD = 10.0
# Rough per-photo cost before any real run has been logged for a model.
ASSUMED_TOKENS = {"input": 4000, "output": 800}


# --- labels ---------------------------------------------------------------


@dataclass
class Label:
    file: str
    expected_id: str
    also_ok: list[str]
    expected_cypher: str
    location: Location | None
    clear: bool
    source: str
    licence: str
    note: str
    cypher_clear: bool = False

    @property
    def is_negative(self) -> bool:
        return not self.expected_id

    @property
    def accepted_ids(self) -> set[str]:
        return {self.expected_id, *self.also_ok} - {""}


def load_labels(path: Path, catalogue: Catalogue) -> list[Label]:
    labels = []
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = set(LABEL_FIELDS) - set(reader.fieldnames or [])
        if missing:
            sys.exit(f"labels.csv is missing columns: {sorted(missing)}")
        for line, row in enumerate(reader, start=2):
            row = {key: (value or "").strip() for key, value in row.items()}
            if not row["file"]:
                continue
            ids = [row["expected_id"], row["expected_cypher"], *row["also_ok"].split("|")]
            for item_id in filter(None, ids):
                if catalogue.get(item_id) is None:
                    sys.exit(f"labels.csv line {line}: unknown item id {item_id!r}")
            cypher = row["expected_cypher"]
            if cypher and catalogue[cypher].parent_id != row["expected_id"]:
                sys.exit(f"labels.csv line {line}: {cypher} needs expected_id {catalogue[cypher].parent_id}")
            location = None
            if row["lat"] or row["lng"]:
                location = Location(
                    lat=float(row["lat"]),
                    lng=float(row["lng"]),
                    accuracy_m=float(row["accuracy_m"] or DEFAULT_ACCURACY_M),
                )
            labels.append(
                Label(
                    file=row["file"],
                    expected_id=row["expected_id"],
                    also_ok=[x for x in row["also_ok"].split("|") if x],
                    expected_cypher=cypher,
                    location=location,
                    clear=row["clear"].lower() in {"y", "yes"},
                    source=row["source"],
                    licence=row["licence"],
                    note=row["note"],
                    cypher_clear=row["cypher_clear"].lower() in {"y", "yes"},
                )
            )
    return labels


# --- running photos -------------------------------------------------------


@dataclass
class Row:
    label: Label
    outcome: str
    item_id: str | None = None
    cypher_id: str | None = None
    reason_code: str = ""
    cypher_reason_code: str | None = None
    answer: ModelAnswer | None = None
    blind_lines: list[str] | None = None
    usage: Usage | None = None
    seconds: float = 0.0
    error: str = ""
    sha256: str = ""

    @property
    def wrong_award(self) -> bool:
        return self.outcome == "AWARD" and self.item_id not in self.label.accepted_ids

    @property
    def wrong_cypher(self) -> bool:
        return self.cypher_id is not None and self.cypher_id != self.label.expected_cypher

    @property
    def correct_award(self) -> bool:
        return self.outcome == "AWARD" and not self.wrong_award

    @property
    def top_confidence(self) -> float | None:
        if self.answer and self.answer.candidates:
            return self.answer.candidates[0].confidence
        return None


def run_photos(labels, photos_dir: Path, client, provider_name: str) -> list[Row]:
    rows = []
    for number, label in enumerate(labels, start=1):
        path = photos_dir / label.file
        print(f"  [{number}/{len(labels)}] {label.file}", file=sys.stderr)
        data = path.read_bytes()
        form = {}
        if label.location:
            form = {
                "lat": str(label.location.lat),
                "lng": str(label.location.lng),
                "accuracy_m": str(label.location.accuracy_m),
            }
        started = time.perf_counter()
        response = client.post(
            "/api/recognise", files={"photo": (label.file, data)}, data=form
        )
        seconds = time.perf_counter() - started
        digest = hashlib.sha256(data).hexdigest()
        if response.status_code != 200:
            rows.append(Row(label, "ERROR", seconds=seconds, sha256=digest,
                            error=f"{response.status_code} {response.text[:200]}"))
            continue
        body = response.json()
        if "answer" not in body:
            sys.exit("the server did not return the model answer: start it with CLOCKED_DEV_MODE=1")
        result = body["result"]
        rows.append(
            Row(
                label,
                outcome=result["outcome"],
                item_id=result["item_id"],
                cypher_id=result["cypher_id"],
                reason_code=result["reason_code"],
                cypher_reason_code=result["cypher_reason_code"],
                answer=ModelAnswer.model_validate(body["answer"]),
                blind_lines=body["blind_lines"],
                usage=Usage.model_validate(body["usage"]),
                seconds=seconds,
                sha256=digest,
            )
        )
    return rows


def rescore(labels, answers_file: Path, catalogue, thresholds) -> list[Row]:
    """Apply the current rules and thresholds to saved model answers. No model calls."""
    saved = {}
    for line in answers_file.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        saved[record["file"]] = record
    rows = []
    for label in labels:
        record = saved.get(label.file)
        if record is None:
            print(f"  no saved answer for {label.file}; skipped", file=sys.stderr)
            continue
        if record.get("error"):
            rows.append(Row(label, "ERROR", error=record["error"], sha256=record["sha256"]))
            continue
        answer = ModelAnswer.model_validate(record["answer"])
        blind_lines = record.get("blind_lines")
        result = verify(answer, catalogue, label.location, thresholds, blind_lines)
        rows.append(
            Row(
                label,
                outcome=result.outcome.value,
                item_id=result.item_id,
                cypher_id=result.cypher_id,
                reason_code=result.reason_code,
                cypher_reason_code=result.cypher_reason_code,
                answer=answer,
                blind_lines=blind_lines,
                usage=Usage(provider=record["provider"], model=record["model"]),
                sha256=record["sha256"],
            )
        )
    return rows


# --- report ---------------------------------------------------------------


def pct(part: int, whole: int) -> str:
    return f"{part}/{whole} ({100 * part / whole:.0f}%)" if whole else "0/0"


def build_report(rows, catalogue, thresholds, meta: dict, ledger: CostLedger) -> str:
    out: list[str] = []
    add = out.append
    positives = [r for r in rows if not r.label.is_negative]
    negatives = [r for r in rows if r.label.is_negative]

    add(f"# Clocked test run {meta['started']}")
    add("")
    add(f"Provider: {meta['provider']}   Model: {meta['model']}   Prompt: {meta['prompt_version']}")
    add(f"Thresholds: high {thresholds.high:.2f}, medium {thresholds.medium:.2f}; "
        f"blind reading: {meta.get('reader', 'same model')}, {meta.get('blind_mode', 'sequential')}")
    add(f"Photos: {len(rows)} ({len(positives)} positives, {len(negatives)} negatives)")
    if meta.get("rescored_from"):
        add(f"Re-scored from saved answers in {meta['rescored_from']} (no model calls)")
    add("")

    wrong = [r for r in rows if r.wrong_award or r.wrong_cypher]
    add(f"## Wrong awards: {len(wrong)}" + ("   (release gate: must be 0)" if wrong else "   OK"))
    for r in wrong:
        expected = r.label.expected_id or "nothing"
        awarded = r.item_id + (f" + {r.cypher_id}" if r.cypher_id else "")
        add(f"- {r.label.file}: awarded {awarded}, expected {expected}"
            + (f" + {r.label.expected_cypher}" if r.label.expected_cypher else ""))
        if r.answer:
            add(f"    reason: {r.answer.reason}")
            for c in r.answer.candidates:
                add(f"    candidate {c.candidate_id} conf {c.confidence:.2f} text {c.object_text}")
            add(f"    other text: {r.answer.other_text}")
            add(f"    blind reading: {r.blind_lines}")
    add("")

    add("## Outcomes")
    add("")
    add("| | AWARD (right) | AWARD (wrong) | RETRY | REJECT | ERROR |")
    add("|---|---|---|---|---|---|")
    for title, group in (("Positives", positives), ("Negatives", negatives)):
        counts = Counter(r.outcome for r in group)
        right = sum(r.correct_award for r in group)
        wrong_n = sum(r.wrong_award for r in group)
        add(f"| {title} | {right} | {wrong_n} | {counts['RETRY']} | {counts['REJECT']} | {counts['ERROR']} |")
    add("")

    clear_common = [
        r for r in positives
        if r.label.clear and catalogue[r.label.expected_id].rarity == "common"
    ]
    awarded = sum(r.correct_award for r in clear_common)
    verdict = "OK" if clear_common and awarded / len(clear_common) >= 0.7 else "BELOW TARGET"
    if not clear_common:
        verdict = "no clear photos of common items labelled"
    add(f"First-time awards, clear photos of common items: {pct(awarded, len(clear_common))}"
        f"   target at least 70%   {verdict}")
    add("")

    add("## Per item")
    add("")
    add("| Item | Name | Photos | Right award | Retry | Reject | Error |")
    add("|---|---|---|---|---|---|---|")
    by_item = defaultdict(list)
    for r in positives:
        by_item[r.label.expected_id].append(r)
    for item_id in sorted(by_item):
        group = by_item[item_id]
        counts = Counter(r.outcome for r in group)
        add(f"| {item_id} | {catalogue[item_id].name} | {len(group)} | "
            f"{sum(r.correct_award for r in group)} | {counts['RETRY']} | {counts['REJECT']} | {counts['ERROR']} |")
    add("")

    cypher_rows = [r for r in rows if r.label.expected_cypher or r.cypher_id or
                   (r.answer and r.answer.cypher_id)]
    if cypher_rows:
        add("## Cyphers")
        add("")
        add("| Photo | Expected | Model said | Awarded | Reason |")
        add("|---|---|---|---|---|")
        for r in cypher_rows:
            said = r.answer.cypher_id if r.answer else None
            add(f"| {r.label.file} | {r.label.expected_cypher or '-'} | {said or '-'} | "
                f"{r.cypher_id or '-'} | {r.cypher_reason_code or '-'} |")
        add("")

    add("## Per photo")
    add("")
    add("| Photo | Expected | Outcome | Item | Reason | Top confidence | Seconds |")
    add("|---|---|---|---|---|---|---|")
    for r in rows:
        flag = " WRONG" if (r.wrong_award or r.wrong_cypher) else ""
        conf = f"{r.top_confidence:.2f}" if r.top_confidence is not None else "-"
        item = (r.item_id or "-") + (f" + {r.cypher_id}" if r.cypher_id else "")
        reason = r.reason_code or r.error
        add(f"| {r.label.file} | {r.label.expected_id or 'negative'} | {r.outcome}{flag} | "
            f"{item} | {reason} | {conf} | {r.seconds:.1f} |")
    add("")

    run_cost = sum(r.usage.cost_usd for r in rows if r.usage)
    add("## Cost")
    add("")
    timed = [r.seconds for r in rows if r.seconds]
    if timed:
        add(f"Latency: median {statistics.median(timed):.1f} s, max {max(timed):.1f} s")
    add(f"This run: ${run_cost:.4f}"
        + (f" (${run_cost / len(rows):.4f} per photo)" if rows else ""))
    add(f"Running total of all logged runs: ${ledger.total_usd():.4f} of ${BUDGET_TOTAL_USD:.2f} "
        f"(warning at ${Settings.budget_stop_usd:.2f})")
    return "\n".join(out)


def save_run(run_dir: Path, rows, report: str, meta: dict) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "summary.md").write_text(report + "\n", encoding="utf-8")
    with open(run_dir / "answers.jsonl", "w", encoding="utf-8") as handle:
        for r in rows:
            record = {
                "file": r.label.file,
                "sha256": r.sha256,
                "provider": meta["provider"],
                "model": meta["model"],
                "prompt_version": meta["prompt_version"],
                "answer": r.answer.model_dump(mode="json") if r.answer else None,
                "blind_lines": r.blind_lines,
                "usage": r.usage.model_dump(mode="json") if r.usage else None,
                "error": r.error,
            }
            handle.write(json.dumps(record) + "\n")
    with open(run_dir / "results.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["file", "expected_id", "expected_cypher", "outcome", "item_id", "cypher_id",
                         "wrong_award", "reason_code", "cypher_reason_code", "top_confidence",
                         "seconds", "cost_usd", "error"])
        for r in rows:
            writer.writerow([
                r.label.file, r.label.expected_id, r.label.expected_cypher, r.outcome,
                r.item_id or "", r.cypher_id or "", r.wrong_award or r.wrong_cypher,
                r.reason_code, r.cypher_reason_code or "",
                "" if r.top_confidence is None else f"{r.top_confidence:.2f}",
                f"{r.seconds:.2f}", f"{r.usage.cost_usd:.6f}" if r.usage else "", r.error,
            ])


# --- budget ---------------------------------------------------------------


def estimated_cost(ledger: CostLedger, model: str, photos: int) -> float:
    average = ledger.average_usd(model)
    if average is None:
        from clocked.recognition.anthropic_provider import cost_usd, load_pricing

        average = cost_usd(load_pricing()[model], ASSUMED_TOKENS["input"], ASSUMED_TOKENS["output"])
    return average * photos


def check_budget(ledger: CostLedger, model: str, photos: int, stop: float, allow_over: bool) -> None:
    spent = ledger.total_usd()
    estimate = estimated_cost(ledger, model, photos)
    print(f"Spent so far ${spent:.4f}. This run: about ${estimate:.4f} for {photos} photos on {model}.",
          file=sys.stderr)
    if spent + estimate > stop and not allow_over:
        sys.exit(f"This run could take the total past ${stop:.2f}. Not running. "
                 "Ask the project owner, then re-run with --yes-over-budget if they agree.")


# --- main -----------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", choices=["anthropic", "fake"], default="anthropic")
    parser.add_argument("--model", default=Settings.model)
    parser.add_argument("--reader-model", help="model for the blind reading (default: --model)")
    parser.add_argument("--blind-mode", choices=["sequential", "parallel"], default="sequential")
    parser.add_argument("--fake-answers", type=Path)
    parser.add_argument("--photos", type=Path, default=REPO_ROOT / "testset" / "photos")
    parser.add_argument("--labels", type=Path, default=REPO_ROOT / "testset" / "labels.csv")
    parser.add_argument("--runs", type=Path, default=REPO_ROOT / "testset" / "runs")
    parser.add_argument("--server", help="URL of a running server (started with CLOCKED_DEV_MODE=1); "
                                         "default runs the endpoint in-process")
    parser.add_argument("--rules-only", type=Path, metavar="RUN_DIR",
                        help="re-score saved answers from an earlier run with current thresholds")
    parser.add_argument("--yes-over-budget", action="store_true")
    args = parser.parse_args(argv)

    settings = Settings.from_env()
    full_catalogue = load_catalogue(settings.csv_path)
    catalogue = load_catalogue(settings.csv_path, settings.disabled_sets)
    thresholds = Thresholds.load()
    ledger = CostLedger(settings.cost_ledger)
    labels = load_labels(args.labels, full_catalogue)

    photo_files = {p.name for p in args.photos.iterdir() if p.suffix.lower() in PHOTO_SUFFIXES}
    unlabelled = sorted(photo_files - {label.file for label in labels})
    if unlabelled:
        print(f"Not in labels.csv, skipped: {', '.join(unlabelled)}", file=sys.stderr)
    missing = [label.file for label in labels if label.file not in photo_files]
    if missing and not args.rules_only:
        sys.exit(f"In labels.csv but not in {args.photos}: {', '.join(missing)}")

    started = datetime.now()
    meta = {
        "started": started.strftime("%Y-%m-%d %H:%M"),
        "provider": args.provider,
        "model": args.model if args.provider != "fake" else "fake",
        "prompt_version": prompt_version(catalogue),
        "reader": args.reader_model or "same model",
        "blind_mode": args.blind_mode,
    }

    if args.rules_only:
        first = json.loads((args.rules_only / "answers.jsonl").read_text().splitlines()[0])
        meta.update(provider=first["provider"], model=first["model"],
                    prompt_version=first["prompt_version"], rescored_from=str(args.rules_only))
        rows = rescore(labels, args.rules_only / "answers.jsonl", catalogue, thresholds)
    else:
        if args.provider != "fake":
            check_budget(ledger, args.model, len(labels), settings.budget_stop_usd, args.yes_over_budget)
        if args.server:
            import httpx

            client = httpx.Client(base_url=args.server, timeout=120)
        else:
            from dataclasses import replace

            from fastapi.testclient import TestClient

            from clocked.app import create_app

            run_settings = replace(
                settings, provider=args.provider, model=args.model,
                reader_model=args.reader_model, blind_mode=args.blind_mode,
                fake_answers=args.fake_answers, dev_mode=True,
                budget_stop_usd=float("inf") if args.yes_over_budget else settings.budget_stop_usd,
                # The per-player limit protects the public server; this run is ours and
                # still has the budget check above.
                rate_per_minute=10**9, rate_per_day=10**9,
            )
            client = TestClient(create_app(run_settings, catalogue=catalogue, thresholds=thresholds))
        rows = run_photos(labels, args.photos, client, args.provider)

    report = build_report(rows, full_catalogue, thresholds, meta, ledger)
    suffix = "rescored" if args.rules_only else meta["model"]
    run_dir = args.runs / f"{started.strftime('%Y%m%d-%H%M%S')}_{meta['provider']}_{suffix}"
    save_run(run_dir, rows, report, meta)
    print(report)
    print(f"\nSaved to {run_dir.relative_to(REPO_ROOT) if run_dir.is_relative_to(REPO_ROOT) else run_dir}")
    return 1 if any(r.wrong_award or r.wrong_cypher for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
