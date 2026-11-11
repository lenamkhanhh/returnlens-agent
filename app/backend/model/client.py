"""Google GenAI Model Adapter for ReturnLens.

Card B02: Model adapter wrapping google-genai SDK.
- Automatic function calling explicitly disabled (manual tool dispatch).
- Pydantic response_schema support for structured output.
- thinking_level and media_resolution per 17 §8.
- Cache disabled when HARNESS_MODE=1 (21 P1).
- ModelRun provenance tracking.
- Clean MODEL_UNAVAILABLE error when key is missing or API call fails.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import os
import time
from typing import Any, Dict, List, Optional, Type, Union

from pydantic import BaseModel

from app.backend.model.exceptions import ModelUnavailableError
from app.backend.model.provenance import ModelRun

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None  # type: ignore
    types = None  # type: ignore


try:
    SDK_VERSION = importlib.metadata.version("google-genai")
except Exception:
    SDK_VERSION = "3.1.0"


def clean_json_schema(schema: Any) -> Any:
    """Clean JSON schema recursively for Gemini API compatibility.

    Strips 'additionalProperties' and 'title' which are rejected by the
    Gemini Developer API (only supported in Enterprise Agent Platform mode).
    """
    if not isinstance(schema, dict):
        return schema
    cleaned: Dict[str, Any] = {}
    for k, v in schema.items():
        if k in ("additionalProperties", "title"):
            continue
        if isinstance(v, dict):
            cleaned[k] = clean_json_schema(v)
        elif isinstance(v, list):
            cleaned[k] = [clean_json_schema(elem) for elem in v]
        else:
            cleaned[k] = v
    return cleaned


class GeminiModelAdapter:
    """Production adapter for Google GenAI with strict safety and governance gates."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        client: Optional[Any] = None,
        harness_mode: Optional[bool] = None,
        primary_model: Optional[str] = None,
        fallback_model: Optional[str] = None,
    ) -> None:
        """Initialize adapter. Accepts injected client for testing."""
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.primary_model = (
            primary_model
            or os.environ.get("MODEL_PRIMARY")
            or "gemini-3.8-flash"
        )
        self.fallback_model = (
            fallback_model
            or os.environ.get("MODEL_FALLBACK")
            or "gemini-3.5-flash-lite"
        )

        if harness_mode is not None:
            self.harness_mode = harness_mode
        else:
            self.harness_mode = os.environ.get("HARNESS_MODE", "0") == "1"

        # In-memory dev/demo response cache (keyed by hash; turned off in harness mode)
        self._dev_cache: Dict[str, Any] = {}

        if client is not None:
            self._client = client
            self.is_available = True
        elif self.api_key and genai is not None:
            try:
                self._client = genai.Client(api_key=self.api_key)
                self.is_available = True
            except Exception:
                self._client = None
                self.is_available = False
        else:
            self._client = None
            self.is_available = False

    def check_availability(self, correlation_id: str = "") -> None:
        """Raises ModelUnavailableError if no valid client or key is configured."""
        if not self.is_available or self._client is None:
            raise ModelUnavailableError(
                message="Model provider unavailable: GEMINI_API_KEY is not configured.",
                code="MODEL_UNAVAILABLE",
                retryable=False,
                correlation_id=correlation_id,
            )

    def _resolve_thinking_level(
        self, stage: str, override: Optional[Any] = None
    ) -> Any:
        """Resolves thinking_level per 17 §8: router minimal; others low."""
        if types is None:
            return None
        if override is not None:
            return override
        if stage == "router":
            return types.ThinkingLevel.MINIMAL
        return types.ThinkingLevel.LOW

    def _resolve_media_resolution(
        self, is_closeup: bool = False, override: Optional[Any] = None
    ) -> Any:
        """Resolves media_resolution per 17 §8 & 21 §A2: low for video/general, high for close-up."""
        if types is None:
            return None
        if override is not None:
            return override
        if is_closeup:
            return types.MediaResolution.MEDIA_RESOLUTION_HIGH
        return types.MediaResolution.MEDIA_RESOLUTION_LOW

    def _compute_input_hashes(self, contents: Union[str, List[Any]]) -> List[str]:
        """Calculates input reference SHA-256 hashes for provenance tracking."""
        hashes = []
        if isinstance(contents, str):
            hashes.append(hashlib.sha256(contents.encode("utf-8")).hexdigest()[:16])
        elif isinstance(contents, list):
            for item in contents:
                if isinstance(item, str):
                    hashes.append(hashlib.sha256(item.encode("utf-8")).hexdigest()[:16])
                elif hasattr(item, "data") and isinstance(item.data, bytes):
                    hashes.append(hashlib.sha256(item.data).hexdigest()[:16])
                else:
                    hashes.append(hashlib.sha256(str(item).encode("utf-8")).hexdigest()[:16])
        return hashes

    def generate(
        self,
        contents: Union[str, List[Any]],
        *,
        stage: str = "general",
        model_id: Optional[str] = None,
        response_schema: Optional[Type[BaseModel]] = None,
        tools: Optional[List[Any]] = None,
        thinking_level: Optional[Any] = None,
        media_resolution: Optional[Any] = None,
        is_closeup_label: bool = False,
        prompt_version: str = "v1",
        schema_version: str = "v1",
        correlation_id: str = "",
        allow_cache: bool = True,
    ) -> tuple[Any, ModelRun]:
        """Execute model generation with strict schema enforcement and provenance.

        Returns:
            Tuple of (raw_response_or_parsed_object, ModelRun)
        """
        self.check_availability(correlation_id=correlation_id)

        target_model = model_id or self.primary_model
        resolved_thinking = self._resolve_thinking_level(stage, thinking_level)
        resolved_media_res = self._resolve_media_resolution(is_closeup_label, media_resolution)
        input_hashes = self._compute_input_hashes(contents)

        # Cache check (strictly bypassed if HARNESS_MODE=1)
        cache_key = ""
        cache_hit = False
        if allow_cache and not self.harness_mode:
            cache_raw = f"{target_model}:{stage}:{prompt_version}:{schema_version}:{':'.join(input_hashes)}"
            cache_key = hashlib.sha256(cache_raw.encode("utf-8")).hexdigest()
            if cache_key in self._dev_cache:
                cached_res, cached_run = self._dev_cache[cache_key]
                replay_run = cached_run.model_copy(
                    update={
                        "run_id": f"RUN-{hashlib.sha256(str(time.time()).encode()).hexdigest()[:12]}",
                        "cache_hit": True,
                        "replay_flag": True,
                    }
                )
                return cached_res, replay_run

        # Build config
        config_kwargs: Dict[str, Any] = {}

        if response_schema is not None:
            config_kwargs["response_mime_type"] = "application/json"
            if hasattr(response_schema, "model_json_schema"):
                config_kwargs["response_schema"] = clean_json_schema(response_schema.model_json_schema())
            elif isinstance(response_schema, dict):
                config_kwargs["response_schema"] = clean_json_schema(response_schema)
            else:
                config_kwargs["response_schema"] = response_schema

        if resolved_thinking is not None:
            config_kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_level=resolved_thinking
            )

        if resolved_media_res is not None:
            config_kwargs["media_resolution"] = resolved_media_res

        # Automatic function calling MUST be disabled (manual tool dispatch per 17 §4)
        if tools:
            config_kwargs["tools"] = tools
            config_kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(
                disable=True
            )
            config_kwargs["tool_config"] = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="ANY")
            )

        config = types.GenerateContentConfig(**config_kwargs) if types else None

        start_time = time.perf_counter()
        max_retries = 1
        last_exc: Optional[Exception] = None
        response = None

        for attempt in range(max_retries + 1):
            try:
                response = self._client.models.generate_content(
                    model=target_model,
                    contents=contents,
                    config=config,
                )
                break
            except Exception as exc:
                last_exc = exc
                err_str = str(exc).lower()

                # Fall back to fallback_model if daily quota limit is exhausted
                if (
                    ("quota exceeded" in err_str or "daily limit" in err_str or "limit: 20" in err_str or "requests per day" in err_str)
                    and target_model != self.fallback_model
                    and self.fallback_model
                ):
                    target_model = self.fallback_model
                    continue

                # Fall back gracefully if model does not support ThinkingLevel.MINIMAL (e.g. gemini-3.8-flash)
                if "thinking level minimal is not supported" in err_str:
                    if config and hasattr(config, "thinking_config"):
                        config.thinking_config = types.ThinkingConfig(
                            thinking_level=types.ThinkingLevel.LOW
                        )
                        continue
                is_retryable = (
                    isinstance(exc, (TimeoutError, ConnectionError))
                    or "429" in err_str
                    or "resource_exhausted" in err_str
                    or "503" in err_str
                    or "502" in err_str
                    or "504" in err_str
                    or "unavailable" in err_str
                    or "timeout" in err_str
                    or "timed out" in err_str
                    or "deadline" in err_str
                )
                # Auth and argument errors must NOT be retried (Test 29)
                is_auth_error = (
                    "401" in err_str
                    or "unauthorized" in err_str
                    or "api_key" in err_str
                    or "403" in err_str
                    or "permission_denied" in err_str
                    or "invalid_argument" in err_str
                )

                if is_auth_error or not is_retryable or attempt >= max_retries:
                    latency_ms = int((time.perf_counter() - start_time) * 1000)
                    raise ModelUnavailableError(
                        message=f"Model call failed: {exc}",
                        code="MODEL_UNAVAILABLE",
                        retryable=is_retryable and not is_auth_error,
                        correlation_id=correlation_id,
                        original_error=exc,
                    ) from exc

                # Transient backoff before 1 retry (03 §7)
                time.sleep(0.05)

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Extract usage metadata
        usage_meta = getattr(response, "usage_metadata", None)
        token_usage = {
            "prompt_tokens": getattr(usage_meta, "prompt_token_count", None),
            "completion_tokens": getattr(usage_meta, "candidates_token_count", None),
            "total_tokens": getattr(usage_meta, "total_token_count", None),
        }

        # Build provenance record
        model_run = ModelRun(
            model_id=target_model,
            sdk_version=SDK_VERSION,
            prompt_version=prompt_version,
            schema_version=schema_version,
            input_ref_hashes=input_hashes,
            output_validated=True,
            cache_hit=False,
            latency_ms=latency_ms,
            token_usage=token_usage,
            replay_flag=False,
        )

        # Store in dev cache if allowed and not in harness mode
        if allow_cache and not self.harness_mode and cache_key:
            self._dev_cache[cache_key] = (response, model_run)

        return response, model_run
