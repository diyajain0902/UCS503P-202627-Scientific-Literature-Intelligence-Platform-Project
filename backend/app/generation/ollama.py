"""Ollama adapter (IR-07, ADR-0001). All Ollama API details stay in this module."""

import logging
import time
from typing import Any

import httpx

from app.core.errors import (
    DependencyUnavailableError,
    GenerationTimeoutError,
    MalformedModelOutputError,
    UpstreamError,
)
from app.generation.provider import GenerationRequest, GenerationResult

logger = logging.getLogger(__name__)


class OllamaProvider:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float,
        num_ctx: int,
        max_tokens: int,
        temperature: float,
        seed: int,
        keep_alive: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model_name = model
        self.options: dict[str, Any] = {
            "num_ctx": num_ctx,
            "num_predict": max_tokens,
            "temperature": temperature,
            "seed": seed,
        }
        self._keep_alive = keep_alive
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            # Connecting should be instant on localhost; generation may take the full timeout.
            timeout=httpx.Timeout(timeout_seconds, connect=5.0),
            transport=transport,
        )

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.post("/api/generate", json=payload)
        except httpx.TimeoutException as exc:
            raise GenerationTimeoutError(
                f"Ollama model '{self.model_name}' did not respond in time"
            ) from exc
        except httpx.TransportError as exc:
            raise DependencyUnavailableError(
                f"Ollama is not reachable ({type(exc).__name__}); start Ollama to use Q&A"
            ) from exc
        if response.status_code == 404:
            raise DependencyUnavailableError(
                f"Ollama model '{self.model_name}' is not installed; "
                f"run: ollama pull {self.model_name}"
            )
        if response.status_code >= 400:
            raise UpstreamError(f"Ollama returned HTTP {response.status_code}")
        try:
            body = response.json()
        except ValueError as exc:
            raise MalformedModelOutputError("Ollama returned a non-JSON HTTP response") from exc
        if not isinstance(body, dict):
            raise MalformedModelOutputError("Ollama returned an unexpected response shape")
        return body

    def generate(self, request: GenerationRequest) -> GenerationResult:
        started = time.perf_counter()
        body = self._post(
            {
                "model": self.model_name,
                "system": request.system,
                "prompt": request.prompt,
                "format": request.json_schema,
                "stream": False,
                "options": self.options,
                "keep_alive": self._keep_alive,
            }
        )
        text = body.get("response")
        if not isinstance(text, str):
            raise MalformedModelOutputError("Ollama response is missing generated text")
        result = GenerationResult(
            text=text,
            model=str(body.get("model") or self.model_name),
            prompt_tokens=body.get("prompt_eval_count"),
            completion_tokens=body.get("eval_count"),
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
            truncated=body.get("done_reason") == "length",
        )
        logger.info(
            "generation_done",
            extra={
                "model": result.model,
                "prompt_tokens": result.prompt_tokens,
                "completion_tokens": result.completion_tokens,
                "duration_ms": result.duration_ms,
                "truncated": result.truncated,
            },
        )
        return result

    def warm_up(self) -> None:
        """Load the model into memory so the first question does not pay the load time."""
        self._post({"model": self.model_name, "prompt": "", "keep_alive": self._keep_alive})
        logger.info("generation_model_loaded", extra={"model": self.model_name})

    def unload(self) -> None:
        """Evict the model from memory (used to measure cold-start latency)."""
        self._post({"model": self.model_name, "prompt": "", "keep_alive": 0})

    def close(self) -> None:
        self._client.close()
