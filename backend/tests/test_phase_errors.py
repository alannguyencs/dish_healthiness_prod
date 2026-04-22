"""
Unit tests for the shared phase-error helpers in src/api/_phase_errors.py.

Both Phase 1 (analyze_image_background) and Phase 2 (trigger_nutrition_analysis_background)
delegate exception handling to these helpers.
"""

# pylint: disable=missing-class-docstring,missing-function-docstring
# pylint: disable=redefined-outer-name,unused-argument

from src.api import _phase_errors
from tests.conftest import make_record


# ---------------------------------------------------------------------------
# classify_phase_error — the five buckets
# ---------------------------------------------------------------------------


class TestClassifyPhaseError:
    def test_missing_api_key_is_config_error(self):
        exc = ValueError("GEMINI_API_KEY environment variable is not set")
        assert _phase_errors.classify_phase_error(exc) == "config_error"

    def test_image_not_found_is_image_missing(self):
        exc = FileNotFoundError("No such file or directory: '/tmp/foo.jpg'")
        assert _phase_errors.classify_phase_error(exc) == "image_missing"

    def test_image_not_found_via_message_is_image_missing(self):
        exc = RuntimeError("image not found at /tmp/foo.jpg")
        assert _phase_errors.classify_phase_error(exc) == "image_missing"

    def test_validation_error_is_parse_error(self):
        exc = ValueError("Pydantic validation failed: missing field 'fat_g'")
        assert _phase_errors.classify_phase_error(exc) == "parse_error"

    def test_503_is_api_error(self):
        exc = RuntimeError("Gemini returned HTTP 503 after 20s")
        assert _phase_errors.classify_phase_error(exc) == "api_error"

    def test_429_is_api_error(self):
        exc = RuntimeError("Rate limit hit: 429 Too Many Requests")
        assert _phase_errors.classify_phase_error(exc) == "api_error"

    def test_timeout_class_is_api_error(self):
        exc = TimeoutError("Read timeout while waiting for Gemini")
        assert _phase_errors.classify_phase_error(exc) == "api_error"

    def test_generic_runtime_error_is_unknown(self):
        exc = RuntimeError("boom")
        assert _phase_errors.classify_phase_error(exc) == "unknown"


# ---------------------------------------------------------------------------
# persist_phase_error — DB write side effects, parameterized on error_key
# ---------------------------------------------------------------------------


class TestPersistPhaseError:
    def _patch_crud(self, monkeypatch, record, captured_writes):
        writes, capture = captured_writes
        monkeypatch.setattr(_phase_errors, "get_dish_image_query_by_id", lambda _id: record)
        monkeypatch.setattr(_phase_errors, "update_dish_image_query_results", capture)
        return writes

    def test_writes_step2_error_with_classified_type(self, monkeypatch, captured_writes):
        record = make_record(result_gemini={"phase": 1, "identification_confirmed": True})
        writes = self._patch_crud(monkeypatch, record, captured_writes)

        _phase_errors.persist_phase_error(
            query_id=7,
            exc=ValueError("GEMINI_API_KEY not set"),
            retry_count=0,
            error_key="nutrition_error",
        )

        written = writes[0]["result_gemini"]
        err = written["nutrition_error"]
        assert err["error_type"] == "config_error"
        assert err["retry_count"] == 0
        assert err["message"] == _phase_errors.ERROR_USER_MESSAGE["config_error"]
        assert err["occurred_at"]

    def test_writes_step1_error_with_classified_type(self, monkeypatch, captured_writes):
        # Phase 1 failure with no prior result_gemini — the helper must
        # initialize the blob.
        record = make_record(result_gemini=None)
        writes = self._patch_crud(monkeypatch, record, captured_writes)

        _phase_errors.persist_phase_error(
            query_id=7,
            exc=FileNotFoundError("/tmp/foo.jpg"),
            retry_count=2,
            error_key="identification_error",
        )

        written = writes[0]["result_gemini"]
        assert written["phase"] == 0  # sentinel for "nothing succeeded yet"
        assert written["identification_data"] is None
        err = written["identification_error"]
        assert err["error_type"] == "image_missing"
        assert err["retry_count"] == 2

    def test_no_op_when_record_missing(self, monkeypatch, captured_writes):
        writes, capture = captured_writes
        monkeypatch.setattr(_phase_errors, "get_dish_image_query_by_id", lambda _id: None)
        monkeypatch.setattr(_phase_errors, "update_dish_image_query_results", capture)

        _phase_errors.persist_phase_error(
            query_id=7, exc=RuntimeError("x"), retry_count=0, error_key="nutrition_error"
        )
        assert writes == []
