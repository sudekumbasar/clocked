"""Claude vision models through the Anthropic API."""

from __future__ import annotations

import base64
import json
import tomllib
from pathlib import Path

import anthropic
from pydantic import ValidationError

from clocked.catalogue import Catalogue
from clocked.recognition.prompt import (
    BLIND_READ_INSTRUCTIONS,
    BLIND_READ_SCHEMA,
    BLIND_READ_USER_TEXT,
    USER_TEXT,
    output_schema,
    system_prompt,
)
from clocked.recognition.provider import BlindRead, ProviderError, ProviderResult
from clocked.recognition.schema import MAX_CANDIDATES, ModelAnswer, Usage

PRICING_FILE = Path(__file__).resolve().parents[1] / "pricing.toml"

# Request options per model. Haiku 4.5 takes no effort setting; on the larger
# models thinking cannot be switched off, so effort is kept low for a short
# classification answer.
MODEL_OPTIONS: dict[str, dict] = {
    "claude-haiku-4-5": {},
    "claude-sonnet-5-5": {"effort": "low"},
    "claude-opus-5-5": {"effort": "low"},
}

MAX_TOKENS = 4000


def load_pricing() -> dict[str, dict[str, float]]:
    with open(PRICING_FILE, "rb") as handle:
        return tomllib.load(handle)["models"]


def cost_usd(pricing: dict[str, float], input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, client: anthropic.Anthropic | None = None):
        prices = load_pricing()
        if model not in prices or model not in MODEL_OPTIONS:
            raise ValueError(f"no pricing or request options for model {model!r}")
        self.model = model
        self.pricing = prices[model]
        self.client = client or anthropic.Anthropic(timeout=60.0, max_retries=2)

    def _request(
        self, image: bytes, media_type: str, system: str, user_text: str, schema: dict
    ) -> dict:
        output_config: dict = {"format": {"type": "json_schema", "schema": schema}}
        effort = MODEL_OPTIONS[self.model].get("effort")
        if effort:
            output_config["effort"] = effort
        return {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "system": system,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64.standard_b64encode(image).decode("ascii"),
                            },
                        },
                        {"type": "text", "text": user_text},
                    ],
                }
            ],
            "output_config": output_config,
        }

    def build_request(self, image: bytes, media_type: str, catalogue: Catalogue) -> dict:
        return self._request(
            image, media_type, system_prompt(catalogue), USER_TEXT, output_schema(catalogue)
        )

    def _call(self, request: dict):
        """Send a request; return (response, usage, raw). None as response means refused."""
        try:
            response = self.client.messages.create(**request)
        except anthropic.AuthenticationError as error:
            raise ProviderError("the API key was rejected") from error
        except anthropic.RateLimitError as error:
            raise ProviderError("rate limited by the model provider") from error
        except anthropic.APIStatusError as error:
            raise ProviderError(f"model provider error {error.status_code}") from error
        except anthropic.APIConnectionError as error:
            raise ProviderError("could not reach the model provider") from error

        usage = Usage(
            provider=self.name,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cost_usd=cost_usd(
                self.pricing, response.usage.input_tokens, response.usage.output_tokens
            ),
        )
        raw = response.model_dump(mode="json")

        if not response.model.startswith(self.model):
            raise ProviderError(f"asked for {self.model} but {response.model} answered")
        if response.stop_reason == "refusal":
            return None, usage, raw
        if response.stop_reason == "max_tokens":
            raise ProviderError("the model's answer was cut off")
        text = next((block.text for block in response.content if block.type == "text"), None)
        if text is None:
            raise ProviderError("the model returned no answer")
        return text, usage, raw

    def read_text(self, image: bytes, media_type: str, filename: str | None = None) -> BlindRead:
        request = self._request(
            image, media_type, BLIND_READ_INSTRUCTIONS, BLIND_READ_USER_TEXT, BLIND_READ_SCHEMA
        )
        text, usage, raw = self._call(request)
        if text is None:
            return BlindRead([], usage, raw)
        try:
            data = json.loads(text)
            lines = [str(line) for line in data["lines"]] if data["readable"] else []
        except (json.JSONDecodeError, KeyError, TypeError) as error:
            raise ProviderError("the model's reading was not in the expected format") from error
        return BlindRead(lines, usage, raw)

    def recognise(
        self, image: bytes, media_type: str, catalogue: Catalogue, filename: str | None = None
    ) -> ProviderResult:
        request = self.build_request(image, media_type, catalogue)
        text, usage, raw = self._call(request)
        if text is None:
            # No answer means nothing can be awarded.
            return ProviderResult(ModelAnswer(reason="model declined"), usage, raw)
        try:
            data = json.loads(text)
            data["candidates"] = data.get("candidates", [])[:MAX_CANDIDATES]
            answer = ModelAnswer.model_validate(data)
        except (json.JSONDecodeError, ValidationError, AttributeError) as error:
            raise ProviderError("the model's answer was not in the expected format") from error
        return ProviderResult(answer, usage, raw)
