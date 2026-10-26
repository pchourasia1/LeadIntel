from typing import Dict, Any, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from schemas.pydantic_schemas import AccountFitLookup
from services.llm_utils import _content_to_text, _extract_json, _resolve_evidence_url

EMPTY_LOOKUP = {
    "manager_portfolio_size": None,
    "property_type": "unknown",
    "detected_pms_vendor": None,
    "evidence": {"manager_portfolio_size": None, "property_type": None, "detected_pms_vendor": None},
}


def _build_user_prompt(property_name: str, full_address: str, manager: Optional[str]) -> str:
    # Q1 and Q3 search by manager name. Without one the queries would literally
    # search for "None", so skip them and tell the model to return null.
    if manager:
        q1 = f"""\
    Q1. manager_portfolio_size
        Issue this query verbatim:
        "{manager}" units OR doors OR "managed properties"
        Then prefer numbers from the manager's own website, NMHC top-50 lists,
        or recent press releases. Take the largest verified figure."""
        q3 = f"""\
    Q3. detected_pms_vendor
        Issue this query verbatim:
        "{manager}" Yardi OR RealPage OR Entrata OR AppFolio OR Buildium OR ResMan
        Only fill this if a result EXPLICITLY names a PMS the manager uses.
        "Hiring someone with Yardi experience" counts; speculation does NOT."""
    else:
        q1 = """\
    Q1. manager_portfolio_size
        The manager is unknown. Do NOT search; set it and its evidence_url to null."""
        q3 = """\
    Q3. detected_pms_vendor
        The manager is unknown. Do NOT search; set it and its evidence_url to null."""

    return f"""\
    Property: {property_name}
    Address:  {full_address}
    Manager:  {manager or 'unknown'}

    Answer THREE independent questions, each with its own search.

{q1}


    Q2. property_type
        Issue this query verbatim:
        "{property_name}" "{full_address}" student OR senior OR affordable OR multifamily
        Map to one of:
        [multifamily, student_housing, affordable_housing, senior_housing,
        single_family_home, commercial_office, hotel, unknown]


{q3}


    Return JSON with EXACTLY this shape. Every answer has a sibling evidence_url
    that MUST be a real URL you saw in search results, or null:

    {{
    "manager_portfolio_size":              <int or null>,
    "manager_portfolio_size_evidence_url": "<url or null>",
    "property_type":                       "<one of the enum values>",
    "property_type_evidence_url":          "<url or null>",
    "detected_pms_vendor":                 "<vendor name or null>",
    "detected_pms_vendor_evidence_url":    "<url or null>"
    }}
    """


def fetch_account_fit_lookup(
    llm_grounded,
    property_name: str,
    full_address: str,
    manager: Optional[str],
) -> Dict[str, Any]:

    sys = SystemMessage(content=(
        "You are a careful B2B sales researcher. Use the google_search tool. "
        "Do NOT answer from prior knowledge. "
        "After your searches, output ONLY a single JSON object as your final text response "
        "- no prose, no fences."
    ))
    user = HumanMessage(content=_build_user_prompt(property_name, full_address, manager))

    try:
        raw = _extract_json(_content_to_text(llm_grounded.invoke([sys, user]).content))
        parsed = AccountFitLookup.model_validate(raw)
    except Exception as e:
        print(f"[account_fit_lookup] parse failed: {e}")
        return {**EMPTY_LOOKUP, "evidence": dict(EMPTY_LOOKUP["evidence"])}

    if not manager:
        # Belt and braces: never trust manager-based answers without a manager.
        parsed.manager_portfolio_size = None
        parsed.manager_portfolio_size_evidence_url = None
        parsed.detected_pms_vendor = None
        parsed.detected_pms_vendor_evidence_url = None

    return {
        "manager_portfolio_size": parsed.manager_portfolio_size,
        "property_type":          parsed.property_type,
        "detected_pms_vendor":    parsed.detected_pms_vendor,
        # Source pages, resolved now because Google's citation links expire.
        "evidence": {
            "manager_portfolio_size": _resolve_evidence_url(parsed.manager_portfolio_size_evidence_url),
            "property_type":          _resolve_evidence_url(parsed.property_type_evidence_url),
            "detected_pms_vendor":    _resolve_evidence_url(parsed.detected_pms_vendor_evidence_url),
        },
    }
