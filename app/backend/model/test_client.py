"""Unit tests for GeminiModelAdapter using a fake client (zero network calls).

Verifies all Card B02 requirements:
- Missing API key -> clean MODEL_UNAVAILABLE error.
- Automatic function calling disabled.
- Pydantic response_schema support.
- thinking_level and media_resolution per 17 §8.
- HARNESS_MODE=1 cache disabling.
- ModelRun provenance tracking.
- Error classification (retryable vs non-retryable).
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from google.genai import types

from app.backend.contracts import Intent, RouterOutput
from app.backend.model.client import GeminiModelAdapter
from app.backend.model.exceptions import ModelUnavailableError


class TestGeminiModelAdapter(unittest.TestCase):
    def test_missing_api_key_raises_model_unavailable(self):
        """Adapter without API key or client must fail cleanly with MODEL_UNAVAILABLE."""
        adapter = GeminiModelAdapter(api_key=None, client=None)
        self.assertFalse(adapter.is_available)

        with self.assertRaises(ModelUnavailableError) as ctx:
            adapter.generate("Hello test", correlation_id="CORR-123")

        err = ctx.exception
        self.assertEqual(err.code, "MODEL_UNAVAILABLE")
        self.assertFalse(err.retryable)
        self.assertEqual(err.correlation_id, "CORR-123")
        self.assertIn("not configured", err.user_message)

    def test_fake_client_structured_output_and_provenance(self):
        """Adapter with fake client generates valid ModelRun provenance."""
        mock_response = MagicMock()
        mock_response.text = '{"intent": "WISMO", "read_tools": [{"name": "get_order", "args": {"order_id": "ORD-7729"}}], "missing_inputs": []}'
        mock_response.usage_metadata.prompt_token_count = 42
        mock_response.usage_metadata.candidates_token_count = 18
        mock_response.usage_metadata.total_token_count = 60

        fake_client = MagicMock()
        fake_client.models.generate_content.return_value = mock_response

        adapter = GeminiModelAdapter(client=fake_client, primary_model="gemini-3.8-flash")
        res, model_run = adapter.generate(
            "Where is my order ORD-7729?",
            stage="router",
            response_schema=RouterOutput,
            prompt_version="v1.0",
            schema_version="v1.0",
        )

        self.assertEqual(res.text, mock_response.text)
        self.assertEqual(model_run.model_id, "gemini-3.8-flash")
        self.assertEqual(model_run.prompt_version, "v1.0")
        self.assertEqual(model_run.schema_version, "v1.0")
        self.assertEqual(model_run.token_usage["prompt_tokens"], 42)
        self.assertEqual(model_run.token_usage["completion_tokens"], 18)
        self.assertEqual(model_run.token_usage["total_tokens"], 60)
        self.assertFalse(model_run.cache_hit)
        self.assertFalse(model_run.replay_flag)

    def test_automatic_function_calling_explicitly_disabled(self):
        """Tools passed to adapter must have automatic_function_calling disabled."""
        fake_client = MagicMock()
        fake_client.models.generate_content.return_value = MagicMock(usage_metadata=None)

        def mock_tool(order_id: str) -> str:
            return "ok"

        adapter = GeminiModelAdapter(client=fake_client)
        adapter.generate(
            "Check order ORD-7729",
            tools=[mock_tool],
        )

        call_args = fake_client.models.generate_content.call_args
        config = call_args.kwargs.get("config")
        self.assertIsNotNone(config)
        self.assertTrue(config.automatic_function_calling.disable)
        self.assertEqual(config.tool_config.function_calling_config.mode, "ANY")

    def test_thinking_level_configurations_per_17_8(self):
        """Router receives MINIMAL thinking; observer/planner receive LOW."""
        fake_client = MagicMock()
        fake_client.models.generate_content.return_value = MagicMock(usage_metadata=None)
        adapter = GeminiModelAdapter(client=fake_client)

        # Stage: router
        adapter.generate("Route message", stage="router")
        cfg_router = fake_client.models.generate_content.call_args.kwargs["config"]
        self.assertEqual(
            cfg_router.thinking_config.thinking_level, types.ThinkingLevel.MINIMAL
        )

        # Stage: observer
        adapter.generate("Observe clip", stage="observer")
        cfg_observer = fake_client.models.generate_content.call_args.kwargs["config"]
        self.assertEqual(
            cfg_observer.thinking_config.thinking_level, types.ThinkingLevel.LOW
        )

        # Stage: planner
        adapter.generate("Plan action", stage="planner")
        cfg_planner = fake_client.models.generate_content.call_args.kwargs["config"]
        self.assertEqual(
            cfg_planner.thinking_config.thinking_level, types.ThinkingLevel.LOW
        )

    def test_media_resolution_configurations_per_17_8(self):
        """General observation uses LOW resolution; close-up label uses HIGH."""
        fake_client = MagicMock()
        fake_client.models.generate_content.return_value = MagicMock(usage_metadata=None)
        adapter = GeminiModelAdapter(client=fake_client)

        # General video/clip
        adapter.generate("Observe video", stage="observer", is_closeup_label=False)
        cfg_general = fake_client.models.generate_content.call_args.kwargs["config"]
        self.assertEqual(
            cfg_general.media_resolution, types.MediaResolution.MEDIA_RESOLUTION_LOW
        )

        # Close-up label image
        adapter.generate("Read label text", stage="observer", is_closeup_label=True)
        cfg_closeup = fake_client.models.generate_content.call_args.kwargs["config"]
        self.assertEqual(
            cfg_closeup.media_resolution, types.MediaResolution.MEDIA_RESOLUTION_HIGH
        )

    def test_harness_mode_strictly_disables_cache(self):
        """When HARNESS_MODE=1, caching is completely disabled (pass^k requirement)."""
        fake_client = MagicMock()
        fake_client.models.generate_content.return_value = MagicMock(usage_metadata=None)

        adapter_harness = GeminiModelAdapter(client=fake_client, harness_mode=True)
        _, run1 = adapter_harness.generate("Identical prompt", allow_cache=True)
        _, run2 = adapter_harness.generate("Identical prompt", allow_cache=True)

        self.assertFalse(run1.cache_hit)
        self.assertFalse(run2.cache_hit)
        self.assertEqual(fake_client.models.generate_content.call_count, 2)

    def test_dev_mode_caching_works(self):
        """When harness_mode=False, dev caching succeeds on identical prompt."""
        fake_client = MagicMock()
        fake_client.models.generate_content.return_value = MagicMock(usage_metadata=None)

        adapter_dev = GeminiModelAdapter(client=fake_client, harness_mode=False)
        _, run1 = adapter_dev.generate("Identical prompt", allow_cache=True)
        _, run2 = adapter_dev.generate("Identical prompt", allow_cache=True)

        self.assertFalse(run1.cache_hit)
        self.assertTrue(run2.cache_hit)
        self.assertTrue(run2.replay_flag)
        self.assertEqual(fake_client.models.generate_content.call_count, 1)

    def test_transient_error_classified_as_retryable(self):
        """Rate limits (429) and 503 errors must be marked retryable."""
        fake_client = MagicMock()
        fake_client.models.generate_content.side_effect = RuntimeError(
            "429 Resource Exhausted: Rate limit exceeded"
        )

        adapter = GeminiModelAdapter(client=fake_client)
        with self.assertRaises(ModelUnavailableError) as ctx:
            adapter.generate("Trigger 429", correlation_id="CORR-429")

        err = ctx.exception
        self.assertEqual(err.code, "MODEL_UNAVAILABLE")
        self.assertTrue(err.retryable)
        self.assertEqual(err.correlation_id, "CORR-429")

    def test_non_transient_error_classified_as_not_retryable(self):
        """Authentication and schema errors must be marked non-retryable."""
        fake_client = MagicMock()
        fake_client.models.generate_content.side_effect = ValueError(
            "401 API_KEY_INVALID"
        )

        adapter = GeminiModelAdapter(client=fake_client)
        with self.assertRaises(ModelUnavailableError) as ctx:
            adapter.generate("Trigger 401", correlation_id="CORR-401")

        err = ctx.exception
        self.assertEqual(err.code, "MODEL_UNAVAILABLE")
        self.assertFalse(err.retryable)

    def test_29_transient_error_retries_once_before_raising_model_unavailable(self):
        """Test 29: Provider transient errors (503, 429, timeout) retry exactly once with backoff."""
        fake_client = MagicMock()
        fake_client.models.generate_content.side_effect = RuntimeError(
            "503 Service Unavailable: The model is currently overloaded. Please try again later."
        )

        adapter = GeminiModelAdapter(client=fake_client)
        with self.assertRaises(ModelUnavailableError) as ctx:
            adapter.generate("Test prompt", correlation_id="CORR-503")

        # Initial call + exactly 1 retry = 2 attempts total
        self.assertEqual(fake_client.models.generate_content.call_count, 2)
        err = ctx.exception
        self.assertEqual(err.code, "MODEL_UNAVAILABLE")
        self.assertTrue(err.retryable)
        self.assertEqual(err.correlation_id, "CORR-503")

    def test_29_transient_error_succeeds_on_second_attempt(self):
        """Test 29: Transient error recovers if retry succeeds within budget."""
        mock_success_response = MagicMock()
        mock_success_response.text = '{"intent": "WISMO"}'
        mock_success_response.usage_metadata = None

        fake_client = MagicMock()
        # First call fails with 429, second call succeeds
        fake_client.models.generate_content.side_effect = [
            RuntimeError("429 Resource Exhausted"),
            mock_success_response,
        ]

        adapter = GeminiModelAdapter(client=fake_client)
        res, model_run = adapter.generate("Test prompt", correlation_id="CORR-RECOVER")

        self.assertEqual(fake_client.models.generate_content.call_count, 2)
        self.assertEqual(res.text, '{"intent": "WISMO"}')
        self.assertTrue(model_run.output_validated)
        self.assertEqual(model_run.model_id, "gemini-3.8-flash")

    def test_29_auth_error_fails_immediately_without_retry(self):
        """Test 29: Authentication / authorization errors must never be retried."""
        fake_client = MagicMock()
        fake_client.models.generate_content.side_effect = ValueError(
            "403 Forbidden: API key not valid. Please pass a valid API key."
        )

        adapter = GeminiModelAdapter(client=fake_client)
        with self.assertRaises(ModelUnavailableError) as ctx:
            adapter.generate("Test prompt", correlation_id="CORR-403")

        # Exactly 1 call: NO retry for auth errors
        self.assertEqual(fake_client.models.generate_content.call_count, 1)
        err = ctx.exception
        self.assertEqual(err.code, "MODEL_UNAVAILABLE")
        self.assertFalse(err.retryable)

    def test_29_no_fake_success_on_failure(self):
        """Test 29: On provider failure, adapter must raise ModelUnavailableError and NEVER fake success."""
        fake_client = MagicMock()
        fake_client.models.generate_content.side_effect = TimeoutError("Deadline exceeded")

        adapter = GeminiModelAdapter(client=fake_client)
        with self.assertRaises(ModelUnavailableError) as ctx:
            adapter.generate("Test prompt")

        err = ctx.exception
        self.assertEqual(err.code, "MODEL_UNAVAILABLE")
        # Ensure ErrorShape contains canonical fields and no fake content
        error_shape = err.to_error_shape()
        self.assertEqual(error_shape["code"], "MODEL_UNAVAILABLE")
        self.assertTrue(error_shape["retryable"])


if __name__ == "__main__":
    unittest.main()
