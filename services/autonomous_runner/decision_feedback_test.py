"""Tests for decision feedback service."""

import pytest

from services.autonomous_runner.decision_feedback import (
    DecisionFeedback,
    DecisionFeedbackService,
    FeedbackType,
)


class TestFeedbackType:
    def test_enum_values(self):
        assert FeedbackType.HELPFUL.value == "helpful"
        assert FeedbackType.NOT_HELPFUL.value == "not_helpful"
        assert FeedbackType.INCORRECT.value == "incorrect"
        assert FeedbackType.EXECUTED.value == "executed"


class TestDecisionFeedback:
    def test_auto_generates_id_and_timestamp(self):
        fb = DecisionFeedback(
            feedback_id="",
            decision_id="dec-1",
            user_id="user-1",
            feedback_type="helpful",
        )
        assert fb.feedback_id  # auto-generated
        assert fb.created_at is not None

    def test_preserves_explicit_id(self):
        fb = DecisionFeedback(
            feedback_id="my-id",
            decision_id="dec-1",
            user_id="user-1",
            feedback_type="helpful",
        )
        assert fb.feedback_id == "my-id"


class TestDecisionFeedbackService:
    def setup_method(self):
        self.service = DecisionFeedbackService(db_pool=None)

    def test_submit_feedback_in_memory(self):
        fb = self.service.submit_feedback(
            decision_id="dec-1",
            user_id="user-1",
            feedback_type="helpful",
            comment="Good signal",
        )
        assert fb.decision_id == "dec-1"
        assert fb.feedback_type == "helpful"
        assert fb.comment == "Good signal"
        assert len(self.service._in_memory) == 1

    def test_submit_feedback_invalid_type(self):
        with pytest.raises(ValueError, match="Invalid feedback type"):
            self.service.submit_feedback(
                decision_id="dec-1",
                user_id="user-1",
                feedback_type="invalid",
            )

    def test_submit_feedback_updates_stats(self):
        self.service.submit_feedback("dec-1", "user-1", "helpful")
        self.service.submit_feedback("dec-2", "user-1", "incorrect")
        self.service.submit_feedback("dec-3", "user-1", "helpful")

        stats = self.service.get_stats()
        assert stats["total_submitted"] == 3
        assert stats["by_type"]["helpful"] == 2
        assert stats["by_type"]["incorrect"] == 1

    def test_get_feedback_for_decision_in_memory(self):
        self.service.submit_feedback("dec-1", "user-1", "helpful")
        self.service.submit_feedback("dec-1", "user-2", "executed")
        self.service.submit_feedback("dec-2", "user-1", "not_helpful")

        results = self.service.get_feedback_for_decision("dec-1")
        assert len(results) == 2
        assert all(r["decision_id"] == "dec-1" for r in results)

    def test_get_feedback_summary_in_memory(self):
        self.service.submit_feedback("dec-1", "user-1", "helpful")
        self.service.submit_feedback("dec-2", "user-1", "executed")

        summary = self.service.get_feedback_summary()
        assert summary["total_submitted"] == 2
        assert summary["by_type"]["helpful"] == 1
        assert summary["by_type"]["executed"] == 1

    def test_get_stats(self):
        stats = self.service.get_stats()
        assert stats["total_submitted"] == 0
        assert stats["in_memory_count"] == 0
        assert stats["db_available"] is False

    def test_all_feedback_types_accepted(self):
        for ft in FeedbackType:
            fb = self.service.submit_feedback("dec-1", "user-1", ft.value)
            assert fb.feedback_type == ft.value

    def test_submit_with_no_comment(self):
        fb = self.service.submit_feedback("dec-1", "user-1", "helpful")
        assert fb.comment is None

    def test_is_available_without_pool(self):
        assert self.service.is_available is False
