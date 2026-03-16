from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import Action, Plan, Review


def test_plan_requires_steps():
    with pytest.raises(ValidationError):
        Plan(
            summary="short but valid summary",
            goals=["goal"],
            risks=[],
            steps=[],
            estimated_minutes=5,
        )


def test_action_rejects_invalid_export_format():
    with pytest.raises(ValidationError):
        Action(
            profile="basic",
            adjustments=[{"op": "exposure", "value": 10, "rationale": "lift subject"}],
            export_format="tiff",
        )


def test_review_requires_notes():
    with pytest.raises(ValidationError):
        Review(decision="approved", approved=True, score=90, notes=[])


def test_review_decision_must_match_approval_flag():
    with pytest.raises(ValidationError):
        Review(decision="revise", approved=True, score=80, notes=["Mismatch"])
