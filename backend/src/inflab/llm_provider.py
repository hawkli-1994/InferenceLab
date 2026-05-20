"""LLM candidate provider backed by LiteLLM."""

from __future__ import annotations

import json
import os
from typing import Any

from pydantic import ValidationError

from inflab.config import LLMProviderSettings
from inflab.schemas import FrameworkParams
from inflab.tuning import CandidateSet


def _extract_content(response: Any) -> str:
    try:
        return response.choices[0].message.content or ""
    except (AttributeError, IndexError):
        return response["choices"][0]["message"]["content"]


def _json_from_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


class LiteLLMCandidateProvider:
    def __init__(self, settings: LLMProviderSettings) -> None:
        self.settings = settings

    def generate(self, context: dict[str, object]) -> CandidateSet:
        if self.settings.provider == "disabled":
            return CandidateSet(candidates=[])
        if not self.settings.model:
            raise ValueError("LLM model is required when provider is enabled")
        if self.settings.api_key:
            key = self.settings.api_key.get_secret_value()
            if self.settings.provider == "anthropic":
                os.environ["ANTHROPIC_API_KEY"] = key
            else:
                os.environ["OPENAI_API_KEY"] = key

        from litellm import completion

        response = completion(
            model=self.settings.model,
            api_base=self.settings.base_url,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Return only JSON with a candidates array. Each candidate must match "
                        "tensor_parallel_size, gpu_memory_utilization, max_num_seqs, "
                        "max_num_batched_tokens, max_model_len, dtype."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(context, sort_keys=True, default=str),
                },
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        try:
            parsed = _json_from_content(_extract_content(response))
            return CandidateSet.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError, KeyError, TypeError) as exc:
            raise ValueError(f"LLM candidate response failed validation: {exc}") from exc


def llm_candidates_or_empty(
    settings: LLMProviderSettings,
    context: dict[str, object],
) -> list[FrameworkParams]:
    provider = LiteLLMCandidateProvider(settings)
    return provider.generate(context).candidates
