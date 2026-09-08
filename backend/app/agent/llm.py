"""Model providers.

Groq free tier rate-limits per model, so the two negotiating sides run on
different models - the advocate on gpt-oss-120b, the provider agent on
gpt-oss-20b. Each gets its own tokens-per-minute bucket, and the split also
reads naturally: the two parties literally think with different weights.

Override either side with ENVOY_MODEL / ENVOY_PROVIDER_MODEL.
"""
from __future__ import annotations

import os
from functools import lru_cache

from strands.models.litellm import LiteLLMModel

from ..config import API_KEY

_PARAMS = {
    "temperature": 0.3,
    "max_tokens": 4000,
    "num_retries": 10,
    "reasoning_effort": "low",
}


def _model(model_id: str) -> LiteLLMModel:
    return LiteLLMModel(
        client_args={"api_key": API_KEY} if API_KEY else {},
        model_id=model_id,
        params=_PARAMS,
    )


@lru_cache(maxsize=4)
def get_model() -> LiteLLMModel:
    """The customer's advocate."""
    return _model(os.getenv("ENVOY_MODEL", "groq/openai/gpt-oss-120b"))


@lru_cache(maxsize=4)
def get_provider_model() -> LiteLLMModel:
    """The company's agent (separate rate-limit bucket on Groq)."""
    return _model(os.getenv("ENVOY_PROVIDER_MODEL", "groq/openai/gpt-oss-20b"))
