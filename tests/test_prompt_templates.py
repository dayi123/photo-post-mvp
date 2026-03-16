from __future__ import annotations

from app.schemas import Plan
from app.services.prompt_templates import action_json_contract, build_action_prompt, build_plan_prompt, resolve_pack


def test_resolve_pack_uses_override_or_model_pattern():
    assert resolve_pack("gpt-5.4") == "gpt-5.4"
    assert resolve_pack("models/gemini-3.1-pro") == "gemini-3.1"
    assert resolve_pack("custom-relay-model") == "default"
    assert resolve_pack("gpt-5.4-mini", "default") == "default"


def test_build_plan_prompt_renders_selected_pack_text():
    rendered = build_plan_prompt(
        original_filename="portrait.jpg",
        model="gpt-5.4-mini",
        override="auto",
    )

    assert rendered.pack == "gpt-5.4"
    assert "Source photo filename: portrait.jpg" in rendered.text
    assert "Do not execute edits" in rendered.text


def test_build_action_prompt_includes_plan_context_and_contract():
    plan = Plan.model_validate(
        {
            "summary": "Prepare a balanced portrait edit with natural skin tones.",
            "goals": ["lift subject visibility", "protect highlights"],
            "risks": ["avoid oversaturation"],
            "steps": [
                {"order": 1, "title": "Tone", "instruction": "Recover bright areas and open shadows."},
                {"order": 2, "title": "Color", "instruction": "Keep white balance neutral."},
            ],
            "estimated_minutes": 8,
        }
    )

    rendered = build_action_prompt(
        plan=plan,
        review_round=2,
        model="relay-model",
        override="auto",
    )

    assert rendered.pack == "default"
    assert "Review round: 2" in rendered.text
    assert "Plan summary: Prepare a balanced portrait edit with natural skin tones." in rendered.text
    assert "1. Tone: Recover bright areas and open shadows." in rendered.text
    assert rendered.contract_summary == action_json_contract()
