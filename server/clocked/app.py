"""The recognition endpoint: one photo in, one structured result out.

Run locally with:  .venv/bin/uvicorn clocked.app:create_app --factory --reload
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.staticfiles import StaticFiles

from clocked.catalogue import REPO_ROOT, Catalogue, Item, load_catalogue
from clocked.config import Settings
from clocked.costs import CostLedger
from clocked.fieldlog import field_record, write_field_record
from clocked.images import ImageError, prepare
from clocked.ratelimit import RateLimiter, client_id
from clocked.recognition.fake_provider import FakeProvider
from clocked.recognition.pipeline import Recogniser
from clocked.recognition.provider import ProviderError, VisionProvider
from clocked.recognition.schema import Location, Usage
from clocked.verification import Thresholds, verify


def make_provider(settings: Settings, model: str | None = None) -> VisionProvider:
    if settings.provider == "fake":
        if settings.fake_answers:
            return FakeProvider.from_file(settings.fake_answers)
        return FakeProvider()
    if settings.provider == "anthropic":
        from clocked.recognition.anthropic_provider import AnthropicProvider

        return AnthropicProvider(model or settings.model)
    raise ValueError(f"unknown provider {settings.provider!r}")


WEB_DIST = REPO_ROOT / "web" / "dist"

# What the app may show about an item. Model hints, match text, radius and notes stay on the server.
# lat and lng place a place item on the map; they are empty (null) for type items.
PUBLIC_FIELDS = ("id", "set", "name", "category", "kind", "rarity", "fact", "clue", "location", "access",
                 "lat", "lng")


def public_item(item: Item) -> dict:
    return {field: getattr(item, field) for field in PUBLIC_FIELDS}


def total_usage(usages: list[Usage]) -> Usage:
    models = list(dict.fromkeys(u.model for u in usages))
    return Usage(
        provider=usages[0].provider,
        model="+".join(models),
        input_tokens=sum(u.input_tokens for u in usages),
        output_tokens=sum(u.output_tokens for u in usages),
        cost_usd=sum(u.cost_usd for u in usages),
    )


def create_app(
    settings: Settings | None = None,
    provider: VisionProvider | None = None,
    catalogue: Catalogue | None = None,
    thresholds: Thresholds | None = None,
    reader: VisionProvider | None = None,
    web_dist: Path | None = WEB_DIST,
) -> FastAPI:
    settings = settings or Settings.from_env()
    catalogue = catalogue or load_catalogue(settings.csv_path, settings.disabled_sets)
    thresholds = thresholds or Thresholds.load()
    provider = provider or make_provider(settings)
    if reader is None:
        same_model = settings.reader_model in (None, settings.model)
        reader = provider if same_model else make_provider(settings, settings.reader_model)
    recogniser = Recogniser(provider, reader, settings.blind_mode)
    ledger = CostLedger(settings.cost_ledger)
    limiter = RateLimiter(settings.rate_per_minute, settings.rate_per_day)

    app = FastAPI(title="Clocked recognition")

    @app.get("/api/items")
    def items() -> list[dict]:
        return [public_item(item) for item in catalogue.items]

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "items": len(catalogue.items)}

    @app.post("/api/recognise")
    def recognise(
        request: Request,
        photo: UploadFile = File(...),
        lat: float | None = Form(None),
        lng: float | None = Form(None),
        accuracy_m: float | None = Form(None),
    ) -> dict:
        given = [value is not None for value in (lat, lng, accuracy_m)]
        if any(given) and not all(given):
            raise HTTPException(422, "send lat, lng and accuracy_m together, or none of them")
        location = Location(lat=lat, lng=lng, accuracy_m=accuracy_m) if all(given) else None

        if not limiter.allow(client_id(request.headers.get("x-forwarded-for"),
                                       request.client.host if request.client else None)):
            raise HTTPException(429, "too many photos in a short time")

        data = photo.file.read(settings.max_upload_bytes + 1)
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(413, "photo too large")
        try:
            image, media_type = prepare(data)
        except ImageError as error:
            raise HTTPException(400, str(error)) from error

        if provider.name != "fake" and ledger.total_usd() >= settings.budget_stop_usd:
            raise HTTPException(503, "model budget stop reached")

        try:
            outcome = recogniser.run(image, media_type, catalogue, filename=photo.filename)
        except ProviderError as error:
            raise HTTPException(502, f"recognition failed: {error}") from error
        for usage in outcome.usages:
            ledger.record(usage, source="api")

        result = verify(outcome.answer, catalogue, location, thresholds, outcome.blind_lines)
        if settings.field_log:
            write_field_record(field_record(outcome.answer, outcome.blind_lines, result, location,
                                            total_usage(outcome.usages)))
        body: dict = {"result": result.model_dump(mode="json")}
        if settings.dev_mode:
            # The model's raw answers and cost, for the test script only.
            body["answer"] = outcome.answer.model_dump(mode="json")
            body["blind_lines"] = outcome.blind_lines
            body["usage"] = total_usage(outcome.usages).model_dump(mode="json")
        return body

    if web_dist is not None and web_dist.is_dir():
        # The built web app, on the same origin as the API. Mounted last so /api wins.
        app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")

    return app

