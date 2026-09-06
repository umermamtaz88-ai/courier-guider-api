"""Build a structured answer from evidence when the LLM is unavailable."""

from __future__ import annotations

from app.ai.context import EvidencePackage
from app.ai.llm.base import StructuredAgentResponse
from app.ai.llm.errors import LLMErrorCode


def build_evidence_fallback_answer(
    evidence: EvidencePackage,
    *,
    answer_type: str,
    intent: str,
    rag_freshness: str,
    using_stored_rag: bool,
    llm_error_code: str | None = None,
) -> StructuredAgentResponse:
    warnings = list(evidence.warnings)
    if using_stored_rag:
        warnings.append(
            "Using stored verified provider information because current web data could not be verified."
        )

    sources = evidence.retrieved_rag_sources[:5] + evidence.web_search_results[:3]
    recommendations = evidence.recommendations

    if recommendations:
        top = recommendations[0]
        provider = top.get("provider", "a courier")
        price = top.get("price") or {}
        price_label = top.get("price_label", "UNAVAILABLE")
        answer_parts = [
            f"For your shipment, **{provider}** is the top stored recommendation based on verified provider data.",
        ]
        if price.get("amount"):
            answer_parts.append(
                f"Stored rate: **{price['amount']} {price.get('currency', 'PKR')}** ({price_label})."
            )
        if len(recommendations) > 1:
            alts = ", ".join(r.get("provider", "?") for r in recommendations[1:3])
            answer_parts.append(f"Alternatives to compare: {alts}.")
        if evidence.retrieved_rag_sources:
            answer_parts.append(
                "Supporting knowledge is drawn from verified stored sources in the knowledge base."
            )
        answer = " ".join(answer_parts)
    elif evidence.retrieved_rag_sources:
        titles = ", ".join(s.get("title", "source") for s in evidence.retrieved_rag_sources[:3])
        answer = (
            "Based on stored verified provider knowledge, here is what we have on file: "
            f"{titles}."
        )
        if llm_error_code == LLMErrorCode.LLM_CONFIGURATION_ERROR:
            answer += " Configure LLM_API_KEY for a fuller synthesized answer."
        else:
            answer += (
                " A fuller synthesized comparison was unavailable from the AI service; "
                "retry in a moment for a complete answer."
            )
    elif llm_error_code == LLMErrorCode.LLM_CONFIGURATION_ERROR:
        answer = (
            "I found limited verified information for this query. "
            "Configure LLM_API_KEY to enable synthesized answers."
        )
    else:
        answer = (
            "I found limited verified information for this query. "
            "Try rephrasing or enabling live web search for richer results."
        )

    return StructuredAgentResponse(
        answer=answer,
        answer_type=answer_type,
        intent=intent,
        recommendations=recommendations,
        assumptions=evidence.missing_information,
        sources=sources,
        warnings=warnings,
    )
