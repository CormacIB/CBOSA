"""
Tests for AIWorker (cbosa/ai/worker.py) — Issue #22.

Tests use a minimal QApplication (provided by the session-scoped qapp fixture)
and cover both the success and error paths through AIWorker's public interface.
"""
from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

from cbosa.ai.worker import AIWorker


# ---------------------------------------------------------------------------
# AIWorker — success path
# ---------------------------------------------------------------------------


class TestAIWorkerSuccess:
    def test_emits_result_ready_with_return_value(self, qapp):
        received: list[str] = []
        worker = AIWorker(lambda: "hello from worker")
        worker.result_ready.connect(received.append)
        worker.start()
        worker.wait()
        QApplication.processEvents()
        assert received == ["hello from worker"]

    def test_does_not_emit_error_on_success(self, qapp):
        errors: list[str] = []
        worker = AIWorker(lambda: "ok")
        worker.error.connect(errors.append)
        worker.start()
        worker.wait()
        QApplication.processEvents()
        assert errors == []

    def test_result_is_coerced_to_str(self, qapp):
        """Callable may return a non-str; AIWorker converts it."""
        received: list[str] = []
        worker = AIWorker(lambda: 42)
        worker.result_ready.connect(received.append)
        worker.start()
        worker.wait()
        QApplication.processEvents()
        assert received == ["42"]


# ---------------------------------------------------------------------------
# AIWorker — error path
# ---------------------------------------------------------------------------


class TestAIWorkerError:
    def test_emits_error_with_exception_message(self, qapp):
        def raise_value_error():
            raise ValueError("something went wrong")

        errors: list[str] = []
        worker = AIWorker(raise_value_error)
        worker.error.connect(errors.append)
        worker.start()
        worker.wait()
        QApplication.processEvents()
        assert len(errors) == 1
        assert "something went wrong" in errors[0]

    def test_does_not_emit_result_ready_on_error(self, qapp):
        def raise_error():
            raise RuntimeError("boom")

        received: list[str] = []
        worker = AIWorker(raise_error)
        worker.result_ready.connect(received.append)
        worker.start()
        worker.wait()
        QApplication.processEvents()
        assert received == []
