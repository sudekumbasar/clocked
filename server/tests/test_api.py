import io
from dataclasses import replace

from fastapi.testclient import TestClient
from PIL import Image

from clocked.app import create_app
from clocked.catalogue import load_catalogue
from clocked.config import Settings
from clocked.recognition.fake_provider import FakeProvider

CATALOGUE = load_catalogue()
HENDRIX = CATALOGUE["P01"]

PLAQUE_ANSWER = {
    "candidates": [{"candidate_id": "P01", "confidence": 0.95, "object_text": ["JIMI HENDRIX"]}],
    "reason": "a blue plaque",
}


def client_for(tmp_path, answers=None, dev_mode=False, blind_reads=None):
    provider = FakeProvider(answers or {}, blind_reads or {})
    settings = replace(
        Settings(), provider="fake", dev_mode=dev_mode, cost_ledger=tmp_path / "ledger.csv"
    )
    return TestClient(create_app(settings, provider=provider, catalogue=CATALOGUE)), provider


def post(client, photo, filename="photo.jpg", **form):
    return client.post("/api/recognise", files={"photo": (filename, photo)}, data=form)


def test_health(tmp_path):
    client, _ = client_for(tmp_path)
    assert client.get("/api/health").json() == {"status": "ok", "items": 70}


def test_award_with_location(tmp_path, photo):
    client, _ = client_for(tmp_path, {"plaque.jpg": PLAQUE_ANSWER},
                           blind_reads={"plaque.jpg": ["JIMI HENDRIX", "1942-1970"]})
    response = post(client, photo, "plaque.jpg", lat=HENDRIX.lat, lng=HENDRIX.lng, accuracy_m=10)
    assert response.status_code == 200
    result = response.json()["result"]
    assert (result["outcome"], result["item_id"], result["message"]) == ("AWARD", "P01", "CLOCKED IT!")


def test_no_location_means_retry(tmp_path, photo):
    client, _ = client_for(tmp_path, {"plaque.jpg": PLAQUE_ANSWER})
    result = post(client, photo, "plaque.jpg").json()["result"]
    assert (result["outcome"], result["reason_code"]) == ("RETRY", "location_missing")


def test_unknown_photo_rejects(tmp_path, photo):
    client, _ = client_for(tmp_path)
    assert post(client, photo).json()["result"]["outcome"] == "REJECT"


def test_partial_location_is_refused(tmp_path, photo):
    client, _ = client_for(tmp_path)
    assert post(client, photo, lat=51.5, lng=-0.1).status_code == 422


def test_not_a_photo_is_refused(tmp_path):
    client, _ = client_for(tmp_path)
    assert post(client, b"not an image").status_code == 400


def test_model_answer_only_in_dev_mode(tmp_path, photo):
    public, _ = client_for(tmp_path)
    assert set(post(public, photo).json()) == {"result"}
    dev, _ = client_for(tmp_path, dev_mode=True)
    assert set(post(dev, photo).json()) == {"result", "answer", "blind_lines", "usage"}


def test_there_is_no_location_override_field(tmp_path, photo):
    # Only lat, lng and accuracy_m are read; anything else is ignored.
    client, _ = client_for(tmp_path, {"plaque.jpg": PLAQUE_ANSWER})
    result = post(client, photo, "plaque.jpg", override_lat=HENDRIX.lat,
                  override_lng=HENDRIX.lng, pretend=1).json()["result"]
    assert result["reason_code"] == "location_missing"


def test_provider_gets_small_jpeg_without_metadata(tmp_path, photo):
    client, provider = client_for(tmp_path)
    post(client, photo)
    sent = provider.calls[0]
    assert sent["media_type"] == "image/jpeg"
    image = Image.open(io.BytesIO(sent["image"]))
    assert max(image.size) == 1568
    assert len(image.getexif()) == 0


def test_fake_provider_costs_are_not_logged(tmp_path, photo):
    client, _ = client_for(tmp_path)
    post(client, photo)
    assert not (tmp_path / "ledger.csv").exists()


def test_blind_reading_runs_only_when_needed(tmp_path, photo):
    answers = {"plaque.jpg": PLAQUE_ANSWER,
               "box.jpg": {"candidates": [{"candidate_id": "S01", "confidence": 0.95}]}}
    client, _ = client_for(tmp_path, answers, dev_mode=True,
                           blind_reads={"plaque.jpg": ["JIMI HENDRIX"], "box.jpg": ["TELEPHONE"]})
    assert post(client, photo, "box.jpg").json()["blind_lines"] is None
    assert post(client, photo, "plaque.jpg").json()["blind_lines"] == ["JIMI HENDRIX"]


def test_plaque_without_blind_reading_match_is_not_awarded(tmp_path, photo):
    client, _ = client_for(tmp_path, {"plaque.jpg": PLAQUE_ANSWER},
                           blind_reads={"plaque.jpg": ["N.PEAL"]})
    result = post(client, photo, "plaque.jpg", lat=HENDRIX.lat, lng=HENDRIX.lng,
                  accuracy_m=10).json()["result"]
    assert (result["outcome"], result["reason_code"]) == ("RETRY", "blind_text_missing")


def test_items_are_public_fields_only(tmp_path):
    client, _ = client_for(tmp_path)
    items = client.get("/api/items").json()
    assert len(items) == 70  # this test client uses the full catalogue
    pub = next(i for i in items if i["id"] == "B01")
    assert pub["name"] == "The Churchill Arms" and pub["category"] == "Pub Crawl"
    for item in items:
        assert set(item) == {"id", "set", "name", "category", "kind", "rarity", "fact", "clue",
                             "location", "access", "lat", "lng"}


def test_default_app_lists_only_version_1_items(tmp_path):
    settings = replace(Settings(), provider="fake", cost_ledger=tmp_path / "ledger.csv")
    client = TestClient(create_app(settings, provider=FakeProvider(), web_dist=None))
    assert len(client.get("/api/items").json()) == 40


def test_serves_the_built_web_app(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<title>Clocked</title>")
    settings = replace(Settings(), provider="fake", cost_ledger=tmp_path / "ledger.csv")
    client = TestClient(create_app(settings, provider=FakeProvider(), web_dist=dist))
    assert "Clocked" in client.get("/").text
    assert client.get("/api/health").json()["status"] == "ok"


def test_items_give_coordinates_for_places_only(tmp_path):
    client, _ = client_for(tmp_path)
    items = {i["id"]: i for i in client.get("/api/items").json()}
    assert (items["L08"]["lat"], items["L08"]["lng"]) == (CATALOGUE["L08"].lat, CATALOGUE["L08"].lng)
    assert items["S04"]["lat"] is None and items["S04"]["lng"] is None
    assert all("radius" not in key and "match" not in key and "hint" not in key for key in items["L08"])


def limited_client(tmp_path, **changes):
    settings = replace(Settings(), provider="fake", cost_ledger=tmp_path / "ledger.csv", **changes)
    return TestClient(create_app(settings, provider=FakeProvider(), catalogue=CATALOGUE, web_dist=None))


def test_too_many_photos_get_429(tmp_path, photo):
    client = limited_client(tmp_path, rate_per_minute=2)
    codes = [post(client, photo).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_the_limit_is_per_player(tmp_path, photo):
    client = limited_client(tmp_path, rate_per_minute=1)
    first = client.post("/api/recognise", files={"photo": ("photo.jpg", photo)},
                        headers={"x-forwarded-for": "203.0.113.5"})
    second = client.post("/api/recognise", files={"photo": ("photo.jpg", photo)},
                         headers={"x-forwarded-for": "203.0.113.6"})
    assert (first.status_code, second.status_code) == (200, 200)


def test_too_large_photo_is_refused(tmp_path, photo):
    client = limited_client(tmp_path, max_upload_bytes=100)
    assert post(client, photo).status_code == 413


def test_field_log_has_no_photo_and_no_coordinates(tmp_path, photo, capsys):
    settings = replace(Settings(), provider="fake", cost_ledger=tmp_path / "ledger.csv", field_log=True)
    provider = FakeProvider({"plaque.jpg": PLAQUE_ANSWER}, {"plaque.jpg": ["JIMI HENDRIX"]})
    client = TestClient(create_app(settings, provider=provider, catalogue=CATALOGUE, web_dist=None))
    post(client, photo, "plaque.jpg", lat=HENDRIX.lat + 0.0002, lng=HENDRIX.lng, accuracy_m=12)
    import json
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    (record,) = [line for line in lines if line.get("event") == "recognition"]
    assert record["item_id"] == "P01" and record["outcome"] == "AWARD"
    assert record["distance_m"] == {"P01": 22} and record["accuracy_m"] == 12
    text = json.dumps(record)
    assert str(HENDRIX.lat)[:6] not in text and "lat" not in record and "lng" not in record
