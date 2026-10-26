"""LLM-drafted outreach email from the configured company to a property-management lead.

Uses enriched features + computed lead_info for personalization.
Returns an OutreachEmail Pydantic model.
"""
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage

import settings
from schemas.pydantic_schemas import OutreachEmail
from services.llm_utils import _content_to_text, _extract_json


def _system_prompt() -> str:
    return (
        f"You are an SDR at {settings.company_name()}, {settings.company_pitch()}. "
        "Draft a short, personalized outbound intro email to ONE lead. "
        "Tone: warm, specific, concise — NOT generic, NOT salesy. "
        "Use ONLY facts that appear in the JSON context provided; never invent "
        "metrics. If a fact is null/missing, omit it. "
        "Output ONLY a JSON object — no prose, no fences."
    )


def _build_user_prompt(lead_row: Dict[str, Any],
                        features: Dict[str, Any],
                        lead_info: Dict[str, Any]) -> str:
    return (
        "Draft a personalized outreach email.\n\n"
        "LEAD:\n"
        f'  - Recipient name:   {lead_row.get("Name")}\n'
        f'  - Recipient email:  {lead_row.get("Email")}\n'
        f'  - Property name:    {lead_row.get("Property Name")}\n'
        f'  - Property address: {lead_row.get("Property Address")}, '
        f'{lead_row.get("City")}, {lead_row.get("State")}\n\n'
        "ENRICHED FEATURES (omit any that are null):\n"
        f"{features}\n\n"
        "WHY THIS LEAD:\n"
        f"  - score:   {lead_info.get('lead_score')}\n"
        f"  - bucket:  {lead_info.get('priority_bucket')}\n"
        f"  - reasons: {lead_info.get('reason_codes')}\n\n"
        "Return JSON with EXACTLY these keys:\n"
        "  - subject: short, specific, no emojis, max ~70 chars\n"
        "  - body:    3–5 sentences. Open with a SPECIFIC observation about "
        "THIS property (units, recent acquisition, hiring, manager, "
        "complaints, etc). End with a soft 15-minute ask. "
        f'Sign off as "{settings.sender_name()}" (no signature block, no title).\n'
        "Hard rules: do NOT use the phrase 'I hope this email finds you well'. "
        "Do NOT exceed 120 words in the body. "
        "Do NOT mention features that were null."
    )


def draft_outreach_email(
    llm,
    lead_row: Dict[str, Any],
    features: Dict[str, Any],
    lead_info: Dict[str, Any],
) -> Optional[OutreachEmail]:
    """Returns an OutreachEmail, or None if generation fails."""
    msgs = [
        SystemMessage(content=_system_prompt()),
        HumanMessage(content=_build_user_prompt(lead_row, features, lead_info)),
    ]
    try:
        resp = llm.invoke(msgs)
        raw = _extract_json(_content_to_text(resp.content))
        return OutreachEmail(
            subject=raw["subject"],
            body=raw["body"],
            drafted_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        print(f"[email_drafter] failed: {e}")
        return None