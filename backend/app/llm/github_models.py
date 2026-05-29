import asyncio
from dataclasses import dataclass

from openai import OpenAI

from app.config import Settings


@dataclass
class LLMResponse:
    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float


class GitHubMarketplaceClient:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client: OpenAI | None = None
        self._api_key = settings.openai_api_key or settings.github_token
        self._base_url = settings.inference_base_url or settings.github_models_endpoint
        if self._api_key:
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
            )

    async def complete(self, *, system_prompt: str, user_prompt: str, model: str) -> LLMResponse:
        if self._settings.mock_llm or self._client is None:
            synthetic = (
                f"[MOCK::{model}] "
                f"Processed request with role prompt '{system_prompt[:70]}...' "
                f"and user input '{user_prompt[:120]}...'"
            )
            prompt_tokens = max(20, len(user_prompt) // 4)
            completion_tokens = max(30, len(synthetic) // 4)
            total = prompt_tokens + completion_tokens
            return LLMResponse(
                content=synthetic,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total,
                estimated_cost_usd=self._estimate_cost_usd(model, total),
            )

        resolved_model = self._resolve_model_name(model)
        response = await asyncio.to_thread(
            self._client.chat.completions.create,
            model=resolved_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content if response.choices else ""
        usage = response.usage
        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        total_tokens = int(getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0)
        return LLMResponse(
            content=content or "",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=self._estimate_cost_usd(resolved_model, total_tokens),
        )

    @staticmethod
    def _estimate_cost_usd(model: str, total_tokens: int) -> float:
        # Conservative placeholder for live dashboarding; pricing can be replaced from model metadata.
        model_rates = {
            "gpt-4o": 0.00001,
            "gpt-4.1": 0.00001,
            "gpt-4.1-mini": 0.000003,
        }
        per_token = model_rates.get(model, 0.000004)
        return round(per_token * total_tokens, 6)

    @staticmethod
    def _resolve_model_name(model: str) -> str:
        normalized = (model or "").strip()
        if not normalized:
            return "gpt-4o"
        if normalized.startswith("openai/"):
            return normalized.split("/", 1)[1]
        model_aliases = {
            "openai/gpt-4.1": "gpt-4.1",
            "openai/gpt-4.1-mini": "gpt-4.1-mini",
        }
        return model_aliases.get(normalized, normalized)
