from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Limits(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    max_searches: int = Field(40, gt=0)
    max_fetches: int = Field(60, gt=0)
    max_tokens: int = Field(400_000, gt=0)
    max_wall_s: float = Field(900.0, gt=0)
    researchers: int = Field(4, gt=0)
    rounds: int = Field(2, gt=0)
    max_topics: int = Field(5, gt=0)
    queries_per_topic: int = Field(2, gt=0)
    results_per_query: int = Field(3, gt=0)
    sources_per_extract: int = Field(3, gt=0)
    source_chars: int = Field(6000, gt=0)
    min_verified_claims: int = Field(2, gt=0)
    max_bytes: int = Field(2_000_000, gt=0)
    fetch_timeout_s: float = Field(20.0, gt=0)


class PlanTopic(BaseModel):
    title: str = Field(min_length=3)
    rationale: str = ""


class PlanOut(BaseModel):
    topics: list[PlanTopic] = Field(min_length=1)


class QueriesOut(BaseModel):
    queries: list[str] = Field(min_length=1)


class LLMCitation(BaseModel):
    source: str
    quote: str


class LLMClaim(BaseModel):
    text: str = Field(min_length=3)
    citations: list[LLMCitation]


class ExtractOut(BaseModel):
    claims: list[LLMClaim]


class WriteOut(BaseModel):
    report_markdown: str = Field(min_length=1)


class SearchHit(BaseModel):
    url: str
    canonical_url: str
    title: str = ""
    snippet: str = ""
    engine: str = ""


class FetchResult(BaseModel):
    url: str
    final_url: str
    canonical_url: str
    status: int
    content_type: str
    bytes: int
    truncated: bool
    text: str | None
    extractor: str | None
    error: str | None
