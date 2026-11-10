"""The Anthropic adapter, tested against a stand-in client. No network, no API key."""

import json
from types import SimpleNamespace

import pytest

from clocked.catalogue import load_catalogue
from clocked.recognition.anthropic_provider import AnthropicProvider
from clocked.recognition.provider import ProviderError

CATALOGUE = load_catalogue()


class StubResponse:
    def __init__(self, text, model="claude-haiku-4-5-20251001", stop_reason="end_turn"):
        self.model = model
        self.stop_reason = stop_reason
        self.content = [SimpleNamespace(type="text", text=text)] if text is not None else []
        self.usage = SimpleNamespace(input_tokens=3000, output_tokens=200)

    def model_dump(self, mode="json"):
        return {"model": self.model, "stop_reason": self.stop_reason}


class StubClient:
    def __init__(self, response):
        self.requests = []
        self.messages = SimpleNamespace(create=self._create)
        self.response = response

    def _create(self, **request):
        self.requests.append(request)
        return self.response


ANSWER = {
    "candidates": [{"candidate_id": "S01", "confidence": 0.9, "object_text": ["TELEPHONE"]}],
    "cypher_id": None,
    "cypher_confidence": 0,
    "other_text": [],
    "reason": "a red phone box",
}


def provider_with(response, model="claude-haiku-4-5"):
    client = StubClient(response)
    return AnthropicProvider(model, client=client), client


def test_parses_answer_and_costs_it():
    provider, _ = provider_with(StubResponse(json.dumps(ANSWER)))
    result = provider.recognise(b"jpeg", "image/jpeg", CATALOGUE)
    assert result.answer.candidates[0].candidate_id == "S01"
    assert result.usage.cost_usd == pytest.approx((3000 * 1.0 + 200 * 5.0) / 1e6)


def test_request_has_photo_schema_and_no_location():
    provider, client = provider_with(StubResponse(json.dumps(ANSWER)))
    provider.recognise(b"jpeg", "image/jpeg", CATALOGUE)
    request = client.requests[0]
    assert request["model"] == "claude-haiku-4-5"
    assert request["output_config"]["format"]["type"] == "json_schema"
    assert "effort" not in request["output_config"]  # Haiku 4.5 takes no effort setting
    assert "thinking" not in request
    content = request["messages"][0]["content"]
    assert content[0]["type"] == "image"
    dumped = json.dumps(request)
    assert '"lat"' not in dumped and '"lng"' not in dumped and "accuracy" not in dumped


def test_larger_models_use_low_effort():
    provider, client = provider_with(StubResponse(json.dumps(ANSWER), model="claude-opus-5-5"),
                                     model="claude-opus-5-5")
    provider.recognise(b"jpeg", "image/jpeg", CATALOGUE)
    assert client.requests[0]["output_config"]["effort"] == "low"


def test_extra_candidates_are_dropped():
    many = dict(ANSWER, candidates=[ANSWER["candidates"][0]] * 3)
    provider, _ = provider_with(StubResponse(json.dumps(many)))
    assert len(provider.recognise(b"jpeg", "image/jpeg", CATALOGUE).answer.candidates) == 2


def test_refusal_is_an_empty_answer():
    provider, _ = provider_with(StubResponse(None, stop_reason="refusal"))
    assert provider.recognise(b"jpeg", "image/jpeg", CATALOGUE).answer.candidates == []


@pytest.mark.parametrize("response", [
    StubResponse(json.dumps(ANSWER), stop_reason="max_tokens"),
    StubResponse("not json"),
    StubResponse(json.dumps(dict(ANSWER, candidates=[{"candidate_id": "S01", "confidence": 7,
                                                      "object_text": []}]))),
    StubResponse(json.dumps(ANSWER), model="claude-sonnet-5-5"),
])
def test_bad_answers_raise_provider_error(response):
    provider, _ = provider_with(response)
    with pytest.raises(ProviderError):
        provider.recognise(b"jpeg", "image/jpeg", CATALOGUE)


def test_unknown_model_is_refused():
    with pytest.raises(ValueError):
        AnthropicProvider("claude-unknown", client=StubClient(None))


def test_blind_read_sends_no_collectible_list():
    reading = json.dumps({"readable": True, "lines": ["E VII R"]})
    provider, client = provider_with(StubResponse(reading))
    result = provider.read_text(b"jpeg", "image/jpeg")
    assert result.lines == ["E VII R"]
    request = json.dumps(client.requests[0])
    for item in CATALOGUE.items:
        assert item.name not in request or item.name in ("VR", "GR")
    assert "S02" not in request and "candidate" not in request


def test_blind_read_unreadable_means_no_lines():
    reading = json.dumps({"readable": False, "lines": ["E II R"]})
    provider, _ = provider_with(StubResponse(reading))
    assert provider.read_text(b"jpeg", "image/jpeg").lines == []
