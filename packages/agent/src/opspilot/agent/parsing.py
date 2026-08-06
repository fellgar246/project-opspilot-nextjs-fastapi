from __future__ import annotations

import json
import re
from typing import Any, cast

from opspilot.agent.providers.base import LLMMessage, LLMProvider, LLMResponse
from opspilot.agent.state.schema import ParseError
from pydantic import BaseModel, ValidationError

PARSE_ERROR_COUNT = 0


def get_parse_error_count() -> int:
    return PARSE_ERROR_COUNT


def reset_parse_error_count() -> None:
    global PARSE_ERROR_COUNT
    PARSE_ERROR_COUNT = 0


def _increment_parse_errors() -> None:
    global PARSE_ERROR_COUNT
    PARSE_ERROR_COUNT += 1


async def parse_structured_output[T: BaseModel](
    provider: LLMProvider,
    *,
    messages: list[LLMMessage],
    response_model: type[T],
    node: str,
    max_repairs: int = 2,
) -> tuple[T | None, LLMResponse, list[ParseError]]:
    errors: list[ParseError] = []
    response = await provider.complete(messages, response_model=response_model)
    parsed = _try_parse(response.content, response_model)
    if parsed is not None:
        return parsed, response, errors

    _increment_parse_errors()
    repair_messages = list(messages)
    for _ in range(max_repairs):
        repair_messages.append(
            LLMMessage(
                role="assistant",
                content=response.content,
            )
        )
        repair_messages.append(
            LLMMessage(
                role="user",
                content=(
                    "Your previous response was invalid JSON for the required schema. "
                    f"Validation error: {_validation_message(response.content, response_model)}. "
                    "Return only valid JSON matching the schema."
                ),
            )
        )
        response = await provider.complete(repair_messages, response_model=response_model)
        parsed = _try_parse(response.content, response_model)
        if parsed is not None:
            return parsed, response, errors
        _increment_parse_errors()

    errors.append(
        ParseError(
            node=node,
            model=response_model.__name__,
            message=_validation_message(response.content, response_model),
        )
    )
    return None, response, errors


def _try_parse[T: BaseModel](content: str | None, response_model: type[T]) -> T | None:
    if not content:
        return None
    payload = _extract_json(content)
    if payload is None:
        return None
    try:
        return response_model.model_validate(payload)
    except ValidationError:
        return None


def _extract_json(content: str) -> dict[str, Any] | list[Any] | None:
    content = content.strip()
    if content.startswith("{") or content.startswith("["):
        try:
            return cast(dict[str, Any] | list[Any], json.loads(content))
        except json.JSONDecodeError:
            pass
    match = re.search(r"(\{.*\}|\[.*\])", content, re.DOTALL)
    if not match:
        return None
    try:
        return cast(dict[str, Any] | list[Any], json.loads(match.group(1)))
    except json.JSONDecodeError:
        return None


def _validation_message(content: str | None, response_model: type[BaseModel]) -> str:
    payload = _extract_json(content or "")
    if payload is None:
        return "invalid JSON"
    try:
        response_model.model_validate(payload)
        return "unknown validation error"
    except ValidationError as exc:
        return exc.errors()[0]["msg"]
