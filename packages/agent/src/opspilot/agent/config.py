from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    model_provider: Literal["mock", "openai"] = Field(
        default="mock", validation_alias="MODEL_PROVIDER"
    )
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", validation_alias="OPENAI_MODEL")
    llm_timeout_seconds: float = Field(default=60.0, validation_alias="LLM_TIMEOUT_SECONDS")

    max_iterations: int = Field(default=12, validation_alias="MAX_AGENT_ITERATIONS")
    max_tokens_per_incident: int = Field(
        default=120_000, validation_alias="MAX_TOKENS_PER_INCIDENT"
    )
    investigation_timeout_seconds: int = Field(
        default=900, validation_alias="INVESTIGATION_TIMEOUT_SECONDS"
    )
    max_tool_calls_per_run: int = Field(default=40, validation_alias="MAX_TOOL_CALLS_PER_RUN")
    confidence_threshold: float = Field(default=0.75, validation_alias="CONFIDENCE_THRESHOLD")
    knowledge_only_confidence_cap: float = Field(
        default=0.6, validation_alias="KNOWLEDGE_ONLY_CONFIDENCE_CAP"
    )
    retrieval_min_score: float = Field(default=0.01, validation_alias="RETRIEVAL_MIN_SCORE")

    prompt_version: str = "v1"


@lru_cache
def get_agent_settings() -> AgentSettings:
    return AgentSettings()
