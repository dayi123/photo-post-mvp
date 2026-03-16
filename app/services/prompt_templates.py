from __future__ import annotations

import json
from dataclasses import dataclass

from app.schemas import AdjustmentOp, Plan, TemplatePackName, TemplatePackOverride


@dataclass(frozen=True)
class RenderedPrompt:
    pack: TemplatePackName
    text: str
    contract_summary: dict[str, object] | None = None


PLAN_TEMPLATES: dict[TemplatePackName, str] = {
    "gpt-5.4": (
        "You are the planning stage in a two-stage photo editing workflow.\n"
        "Produce idea-level guidance only. Do not execute edits, call tools, or emit JSON.\n"
        "Return a concise plan with summary, goals, risks, ordered steps, and estimated_minutes.\n"
        "Source photo filename: {original_filename}"
    ),
    "gemini-3.1": (
        "Role: planning stage for a photo editing assistant.\n"
        "Stay at the intent level. Do not produce executable actions or machine JSON.\n"
        "Describe the approved direction using summary, goals, risks, numbered steps, and estimated_minutes.\n"
        "Input filename: {original_filename}"
    ),
    "default": (
        "Create a brief photo-edit plan for the uploaded image.\n"
        "This is the planning stage only, so keep it conceptual and non-executable.\n"
        "Include summary, goals, risks, ordered steps, and estimated_minutes.\n"
        "Filename: {original_filename}"
    ),
}

ACTION_TEMPLATES: dict[TemplatePackName, str] = {
    "gpt-5.4": (
        "You are the action stage in a two-stage photo editing workflow.\n"
        "Convert the approved plan into edit instructions.\n"
        "Return strict JSON only. No markdown, no prose, no code fences.\n"
        "Review round: {review_round}\n"
        "{plan_context}\n"
        "JSON contract summary:\n"
        "{contract_summary}"
    ),
    "gemini-3.1": (
        "Role: action stage for a photo editing assistant.\n"
        "Translate the approved plan into a machine-readable edit payload.\n"
        "Output must be valid JSON only and must satisfy the contract below.\n"
        "Review round: {review_round}\n"
        "{plan_context}\n"
        "JSON contract summary:\n"
        "{contract_summary}"
    ),
    "default": (
        "Generate the photo editing action payload from the approved plan.\n"
        "Output JSON only and follow the contract exactly.\n"
        "Review round: {review_round}\n"
        "{plan_context}\n"
        "JSON contract summary:\n"
        "{contract_summary}"
    ),
}


def resolve_pack(model: str, override: TemplatePackOverride = "auto") -> TemplatePackName:
    if override != "auto":
        return override

    normalized = model.strip().lower()
    if "gpt-5.4" in normalized:
        return "gpt-5.4"
    if "gemini-3.1" in normalized:
        return "gemini-3.1"
    return "default"


def build_plan_prompt(
    original_filename: str,
    model: str,
    override: TemplatePackOverride = "auto",
) -> RenderedPrompt:
    pack = resolve_pack(model, override)
    return RenderedPrompt(pack=pack, text=PLAN_TEMPLATES[pack].format(original_filename=original_filename))


def build_action_prompt(
    plan: Plan,
    review_round: int,
    model: str,
    override: TemplatePackOverride = "auto",
) -> RenderedPrompt:
    pack = resolve_pack(model, override)
    contract = action_json_contract()
    return RenderedPrompt(
        pack=pack,
        text=ACTION_TEMPLATES[pack].format(
            review_round=review_round,
            plan_context=_render_plan_context(plan),
            contract_summary=json.dumps(contract, indent=2, ensure_ascii=True),
        ),
        contract_summary=contract,
    )


def action_json_contract() -> dict[str, object]:
    return {
        "type": "object",
        "required": ["profile", "adjustments", "export_format"],
        "profile": "string length 3-100",
        "adjustments": {
            "type": "array",
            "min_items": 1,
            "max_items": 12,
            "item": {
                "op": [member.value for member in AdjustmentOp],
                "value_range": [-100.0, 100.0],
                "rationale": "string length 5-200",
            },
        },
        "export_format": ["jpg", "jpeg", "png"],
    }


def _render_plan_context(plan: Plan) -> str:
    step_lines = [f"{step.order}. {step.title}: {step.instruction}" for step in plan.steps]
    return "\n".join(
        [
            f"Plan summary: {plan.summary}",
            f"Goals: {', '.join(plan.goals)}",
            f"Risks: {', '.join(plan.risks) if plan.risks else 'none'}",
            "Plan steps:",
            *step_lines,
        ]
    )
