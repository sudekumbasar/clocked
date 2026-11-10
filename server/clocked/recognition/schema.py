"""What the vision model returns, and what the server returns to the app."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

MAX_CANDIDATES = 2


class Candidate(BaseModel):
    candidate_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    object_text: list[str] = Field(default_factory=list)


class ModelAnswer(BaseModel):
    """The model's structured answer. It never awards anything by itself."""

    candidates: list[Candidate] = Field(default_factory=list, max_length=MAX_CANDIDATES)
    cypher_id: str | None = None
    cypher_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    other_text: list[str] = Field(default_factory=list)
    # True when the item is a picture of it (a screen, a poster, a print), not the real thing.
    photo_of_picture: bool = False
    reason: str = ""


class Usage(BaseModel):
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class Location(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    accuracy_m: float = Field(ge=0)


class Outcome(str, Enum):
    AWARD = "AWARD"
    RETRY = "RETRY"
    REJECT = "REJECT"


class CandidateCheck(BaseModel):
    """The verification result for one candidate."""

    candidate_id: str
    outcome: Outcome
    reason_code: str
    distance_m: float | None = None


class Result(BaseModel):
    outcome: Outcome
    item_id: str | None = None
    cypher_id: str | None = None
    message: str
    reason_code: str
    cypher_reason_code: str | None = None
    checks: list[CandidateCheck] = Field(default_factory=list)
