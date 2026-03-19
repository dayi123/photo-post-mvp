from __future__ import annotations

from app.schemas import Action, ActionAdjustment, Plan, PlanStep, Review, ReviewDecision


def generate_plan(original_filename: str, desired_effect: str | None = None) -> Plan:
    base_name = original_filename.rsplit(".", 1)[0]
    summary = f"Prepare a clean social-ready edit for {base_name} with balanced tone and detail."
    if desired_effect:
        summary = f"Target user desired effect: {desired_effect}. " + summary
    return Plan(
        summary=summary,
        goals=["recover highlights", "lift subject visibility", "keep natural color"],
        risks=["avoid oversaturation", "protect skin texture"],
        steps=[
            PlanStep(order=1, title="Tone balance", instruction="Recover bright areas and lift shadow detail."),
            PlanStep(order=2, title="Color cleanup", instruction="Keep whites neutral and avoid heavy tint shifts."),
            PlanStep(order=3, title="Framing pass", instruction="Apply a light crop only if it improves focus."),
        ],
        estimated_minutes=8,
    )


def generate_action(plan: Plan, review_round: int) -> Action:
    exposure = 12.0 if review_round == 1 else 8.0
    saturation = 6.0 if review_round == 1 else 3.0
    return Action(
        profile="social-natural-v1",
        adjustments=[
            ActionAdjustment(op="exposure", value=exposure, rationale=plan.goals[1]),
            ActionAdjustment(op="highlights", value=-18.0, rationale=plan.goals[0]),
            ActionAdjustment(op="shadows", value=20.0, rationale="Open darker regions."),
            ActionAdjustment(op="saturation", value=saturation, rationale=plan.goals[2]),
            ActionAdjustment(op="crop", value=5.0, rationale="Tighten composition slightly."),
        ],
        export_format="jpg",
    )


def review_output(review_round: int) -> Review:
    if review_round < 2:
        return Review(
            decision=ReviewDecision.revise,
            approved=False,
            score=74,
            notes=["Highlights improved but color is still slightly strong."],
            next_focus="Reduce saturation and keep the edit more natural.",
        )
    return Review(
        decision=ReviewDecision.approved,
        approved=True,
        score=91,
        notes=["Image looks balanced and ready for export."],
        next_focus=None,
    )

