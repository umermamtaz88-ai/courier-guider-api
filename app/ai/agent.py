import json
import re
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.context import AgentContext, EvidencePackage, chunk_to_source_dict
from app.ai.fallback_answer import build_evidence_fallback_answer
from app.ai.intents import Intent, IntentDetector
from app.ai.llm.base import StructuredAgentResponse
from app.ai.llm.errors import LLMError, LLMErrorCode
from app.ai.llm.factory import get_llm_provider
from app.ai.memory.long_memory import LongMemoryService
from app.ai.memory.short_memory import ShortMemoryService
from app.ai.pipeline_trace import PipelineErrorCode, PipelineTrace
from app.ai.prompts import PROMPT_VERSION, load_courier_guider_prompt
from app.ai.providers_catalog import (
    detect_providers_in_text,
    normalize_provider_list,
)
from app.ai.query_normalizer import normalize_query
from app.ai.rag import RAGService
from app.ai.rag.identifier_search import search_by_identifiers
from app.ai.research_sources import ensure_inline_citations, normalize_sources, research_indicator
from app.ai.tool_loop import ToolLoop
from app.ai.tools.carrier_tools import CarrierTools
from app.ai.tools.registry import TOOL_REGISTRY, Permission
from app.ai.tools.shipment_tools import ShipmentTools
from app.config import get_settings
from app.db.models import AgentRun, Conversation, Message, ShipmentIssue
from app.logging import get_logger
from app.search.carrier_registry import DEFAULT_COMPARE_CARRIERS, display_name, resolve_carriers
from app.search.evidence_blocks import assign_source_ids, format_evidence_blocks
from app.search.query_plan import classify_query_plan
from app.services.attachments.attachment_service import AttachmentService
from app.services.comparison.comparison_engine import ComparisonEngine
from app.services.web_search.web_search_service import WebSearchService
from app.utils.pii import redact_pii

logger = get_logger("courier_guider.agent")


def _rag_provider_coverage(rag_sources: list[dict], providers: list[str]) -> int:
    """How many requested providers already have at least one RAG hit."""
    from app.ai.providers_catalog import infer_provider_from_source

    covered: set[str] = set()
    for src in rag_sources or []:
        name = src.get("provider") or infer_provider_from_source(
            publisher=src.get("publisher"),
            title=src.get("title"),
            url=src.get("url"),
        )
        if name:
            covered.add(name)
    return sum(1 for p in providers if p in covered)


class CourierGuiderAgent:
    """RAG-first courier advisor: memory + knowledge + optional web search → LLM."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.intents = IntentDetector()
        self.rag = RAGService(db)
        self.short_memory = ShortMemoryService(db)
        self.long_memory = LongMemoryService(db)
        self.comparison = ComparisonEngine(db)
        self.web_search = WebSearchService(db)
        self.attachments = AttachmentService(db)
        self.shipment_tools = ShipmentTools(db)
        self.carrier_tools = CarrierTools(db)
        self.tool_loop = ToolLoop(db)

    async def run(
        self,
        *,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        message: str,
        conversation_id: uuid.UUID | None = None,
        shipment_id: uuid.UUID | None = None,
        priority: str = "balanced",
    ) -> dict:
        start = time.monotonic()
        trace = PipelineTrace(query=message)
        normalized_message = normalize_query(message)
        intent = self.intents.detect(normalized_message)
        trace.detected_intent = intent.value
        trace.log_stage("intent_detection", detected_intent=intent.value)
        conversation = await self._get_or_create_conversation(
            tenant_id, user_id, conversation_id, shipment_id, message
        )

        if intent == Intent.GREETING:
            return await self._greeting_response(
                conversation=conversation,
                tenant_id=tenant_id,
                user_id=user_id,
                message=message,
                shipment_id=shipment_id,
                trace=trace,
            )

        parsed = await self.short_memory.build_context(
            conversation_id=conversation.id,
            tenant_id=tenant_id,
            message=normalized_message,
            intent=intent.value,
        )
        parsed.priority = priority or parsed.priority
        trace.extracted_providers = parsed.providers
        trace.extracted_weight = parsed.weight_kg
        trace.extracted_origin = parsed.origin
        trace.extracted_destination = parsed.destination
        trace.log_stage(
            "query_extraction",
            extracted_providers=parsed.providers,
            extracted_weight=parsed.weight_kg,
            extracted_origin=parsed.origin,
            extracted_destination=parsed.destination,
        )
        trace.extracted_providers = parsed.providers
        trace.extracted_weight = parsed.weight_kg
        trace.extracted_origin = parsed.origin
        trace.extracted_destination = parsed.destination
        trace.log_stage(
            "query_extraction",
            extracted_providers=parsed.providers,
            extracted_weight=parsed.weight_kg,
            extracted_origin=parsed.origin,
            extracted_destination=parsed.destination,
        )
        long_mem = await self.long_memory.load(tenant_id, user_id)
        if long_mem.get("preferred_priority"):
            parsed.priority = long_mem["preferred_priority"].get("value", parsed.priority)
        if not parsed.origin and long_mem.get("default_origin"):
            parsed.origin = long_mem["default_origin"].get("value")

        evidence = EvidencePackage(
            query=message,
            intent=intent.value,
            answer_type=parsed.intent,
            parsed_query=parsed.to_dict(),
            short_memory=await self.short_memory.load(conversation.id),
            long_memory=long_mem,
            preferences={"priority": parsed.priority, "normalized_query": normalized_message},
        )

        identifier_hits = await search_by_identifiers(self.db, tenant_id=tenant_id, query=message)
        if identifier_hits:
            evidence.database_facts.append({"type": "identifier_matches", "data": identifier_hits})

        if shipment_id:
            await self._attach_shipment_context(evidence, tenant_id, shipment_id)

        chunks = await self.rag.retrieve(normalized_message, tenant_id=tenant_id, shipment_id=shipment_id)
        evidence.retrieved_rag_sources = [chunk_to_source_dict(c) for c in chunks]
        rag_used = len(chunks) > 0
        trace.rag_result_count = len(chunks)
        trace.rag_top_sources = [
            {
                "title": s.get("title"),
                "publisher": s.get("publisher"),
                "freshness": s.get("freshness"),
                "final_score": s.get("final_score"),
            }
            for s in evidence.retrieved_rag_sources[:5]
        ]
        # Only flag missing RAG when this query actually needed knowledge retrieval
        if not rag_used and self.intents.needs_rag(intent):
            trace.add_error(PipelineErrorCode.RAG_NO_RESULTS)

        rag_freshness = "unknown"
        if evidence.retrieved_rag_sources:
            labels = [s.get("freshness", "unknown") for s in evidence.retrieved_rag_sources]
            if any(x == "expired" for x in labels):
                rag_freshness = "expired"
            elif any(x == "stale" for x in labels):
                rag_freshness = "stale"
            elif any(x == "current" for x in labels):
                rag_freshness = "current"
            elif any(x == "recent" for x in labels):
                rag_freshness = "recent"
        trace.rag_freshness = rag_freshness
        if rag_freshness in ("stale", "expired"):
            trace.add_error(PipelineErrorCode.RAG_STALE)

        parsed.providers = normalize_provider_list(
            parsed.providers or detect_providers_in_text(normalized_message)
        )
        query_plan = classify_query_plan(
            message,
            rag_hit_count=len(chunks),
            rag_freshness=rag_freshness,
        )
        # Prefer resolved carriers from query plan; keep legacy display names for parser
        plan_carriers = list(query_plan.carriers)
        if not plan_carriers and parsed.providers:
            plan_carriers = resolve_carriers(" ".join(parsed.providers))

        search_providers = [display_name(c) for c in plan_carriers]
        if (
            query_plan.intent == "comparison"
            or intent in (Intent.COMPARE_PROVIDERS, Intent.GET_SHIPPING_QUOTE, Intent.PLAN_SHIPMENT)
            or parsed.intent == "provider_comparison"
        ) and not search_providers:
            search_providers = [display_name(c) for c in DEFAULT_COMPARE_CARRIERS]
            plan_carriers = list(DEFAULT_COMPARE_CARRIERS)

        web_search_used = False
        current_data_verified = False
        data_source = "none"
        using_stored_rag_fallback = False
        web_search_error_code: str | None = None
        web_search_retryable = False
        request_id = str(uuid.uuid4())
        web_search_requested = query_plan.needs_live_search or self.web_search.needs_web_search(
            message,
            rag_hit_count=len(chunks),
            rag_freshness=rag_freshness,
            intent=intent.value,
        )
        # Named provider questions: verify official sites when RAG lacks each provider
        if search_providers and _rag_provider_coverage(
            evidence.retrieved_rag_sources, search_providers
        ) < len(search_providers):
            web_search_requested = True
        trace.web_search_requested = web_search_requested
        trace.extracted_providers = search_providers or plan_carriers
        logger.info(
            "query_plan",
            request_id=request_id,
            query=message[:120],
            intent=query_plan.intent,
            carriers=plan_carriers,
            needs_live_search=web_search_requested,
            rag_result_count=len(chunks),
        )
        trace.log_stage("freshness_check", rag_freshness=rag_freshness, web_search_requested=web_search_requested)

        if web_search_requested:
            try:
                if search_providers or plan_carriers:
                    web_outcome = await self.web_search.search_for_providers(
                        tenant_id=tenant_id,
                        message=message,
                        providers=search_providers or plan_carriers,
                        topics=parsed.topics,
                        country=parsed.country or "Pakistan",
                        intent=query_plan.intent,
                        request_id=request_id,
                    )
                else:
                    search_q = self.web_search.build_query(
                        message,
                        providers=parsed.providers,
                        topics=parsed.topics,
                        country=parsed.country or "Pakistan",
                    )
                    domains = self.web_search.domains_for_providers(parsed.providers)
                    web_outcome = await self.web_search.search(
                        tenant_id=tenant_id,
                        query=search_q,
                        domains=domains,
                    )
            except Exception as exc:
                logger.exception("web_search_unexpected_error", error=str(exc)[:300])
                from app.services.web_search.web_search_service import WebSearchOutcome

                web_outcome = WebSearchOutcome(
                    provider=self.settings.web_search_provider,
                    requested=True,
                    error_code=PipelineErrorCode.WEB_SEARCH_UNKNOWN_ERROR,
                    error_message=str(exc)[:300],
                )

            trace.web_search_provider = web_outcome.provider
            trace.tavily_http_status = web_outcome.http_status
            trace.tavily_response_summary = (
                web_outcome.error_message
                if web_outcome.error_code
                else f"{len(web_outcome.results)} results from {web_outcome.provider}"
            )
            trace.web_result_count = len(web_outcome.results)
            trace.web_domains = web_outcome.domains
            trace.log_stage(
                "web_search",
                web_search_provider=web_outcome.provider,
                tavily_http_status=web_outcome.http_status,
                web_result_count=len(web_outcome.results),
                web_domains=web_outcome.domains,
            )

            if web_outcome.error_code:
                trace.add_error(web_outcome.error_code)
                web_search_error_code = web_outcome.error_code
                web_search_retryable = web_outcome.retryable
            if web_outcome.results:
                evidence.web_search_results = web_outcome.results
                web_search_used = True
                current_data_verified = not bool(web_outcome.error_code)
                data_source = "web" if not rag_used else "mixed"
                trace.source_extraction_ok = True
            elif web_outcome.error_code and rag_used and rag_freshness != "expired":
                using_stored_rag_fallback = True
                evidence.warnings.append(
                    "I couldn't verify the latest web information, so I'm using the stored verified knowledge below."
                )
                trace.warnings.append(evidence.warnings[-1])
            elif web_outcome.error_code:
                evidence.warnings.append(
                    "I couldn't verify the latest web information, so I'm using the stored verified knowledge below."
                )
                trace.warnings.append(evidence.warnings[-1])

        if rag_used and not web_search_used:
            data_source = "rag"
            using_stored_rag_fallback = web_search_requested
            if rag_freshness in ("current", "recent"):
                current_data_verified = False

        # Private chat attachments (never global RAG)
        for att in await self.attachments.get_for_conversation(tenant_id, conversation.id):
            if att.extracted_text:
                evidence.private_attachments.append(
                    {
                        "id": str(att.id),
                        "filename": att.filename,
                        "scope": att.scope,
                        "status": att.processing_status,
                        "excerpt": att.extracted_text[:2000],
                        "label": "USER_PROVIDED",
                    }
                )

        if intent in (Intent.COMPARE_PROVIDERS, Intent.GET_SHIPPING_QUOTE, Intent.PLAN_SHIPMENT) or parsed.intent == "provider_comparison":
            comparison = await self.comparison.compare(parsed)
            evidence.recommendations = comparison.get("recommendations", [])
            evidence.warnings.extend(comparison.get("warnings", []))
            if comparison.get("assumptions"):
                evidence.missing_information.extend(comparison.get("assumptions", []))

        if self.intents.needs_live_data(intent) and shipment_id and evidence.shipment:
            evidence.current_live_data.extend(
                await self._fetch_live_tracking(tenant_id, shipment_id, evidence)
            )

        context = AgentContext(
            tenant_id=tenant_id,
            user_id=user_id,
            shipment_id=shipment_id,
            intent=intent.value,
            evidence=evidence,
            allowed_tools=[n for n, p in TOOL_REGISTRY.items() if p == Permission.READ],
        )

        trace.evidence_count = (
            len(evidence.retrieved_rag_sources)
            + len(evidence.web_search_results)
            + len(evidence.recommendations)
            + len(evidence.database_facts)
        )
        if trace.evidence_count == 0:
            trace.add_error(PipelineErrorCode.EVIDENCE_EMPTY)
        trace.log_stage("evidence_package", evidence_count=trace.evidence_count)

        trace.evidence_count = (
            len(evidence.retrieved_rag_sources)
            + len(evidence.web_search_results)
            + len(evidence.recommendations)
            + len(evidence.database_facts)
        )
        if trace.evidence_count == 0:
            trace.add_error(PipelineErrorCode.EVIDENCE_EMPTY)
        trace.log_stage("evidence_package", evidence_count=trace.evidence_count)

        agent_run = AgentRun(
            tenant_id=tenant_id,
            conversation_id=conversation.id,
            shipment_id=shipment_id,
            status="started",
            model=self.settings.llm_model,
            prompt_version=PROMPT_VERSION,
            intent=intent.value,
            retrieval_count=len(evidence.retrieved_rag_sources),
        )
        self.db.add(agent_run)
        await self.db.flush()
        self.db.add(Message(conversation_id=conversation.id, role="user", content=message))

        llm_success = True
        llm_error_code: str | None = None
        llm_retryable = False
        llm_retry_after: float | None = None

        llm_success = True
        llm_error_code: str | None = None
        llm_retryable = False
        llm_retry_after: float | None = None

        try:
            parsed_response: StructuredAgentResponse
            if not self.settings.llm_api_key:
                llm_success = False
                llm_error_code = PipelineErrorCode.LLM_API_KEY_MISSING
                trace.add_error(PipelineErrorCode.LLM_API_KEY_MISSING)
                parsed_response = build_evidence_fallback_answer(
                    evidence,
                    answer_type=parsed.intent,
                    intent=intent.value,
                    rag_freshness=rag_freshness,
                    using_stored_rag=using_stored_rag_fallback or (rag_used and not web_search_used),
                )
                trace.response_type = parsed_response.answer_type
                trace.llm_received_evidence = trace.evidence_count > 0
            else:
                trace.llm_received_evidence = trace.evidence_count > 0
                if not trace.llm_received_evidence:
                    trace.add_error(PipelineErrorCode.LLM_CONTEXT_EMPTY)
                try:
                    llm = get_llm_provider()
                    messages = [
                        {"role": "system", "content": load_courier_guider_prompt()},
                        {"role": "user", "content": self._build_user_prompt(context)},
                    ]
                    llm_response = await llm.generate(
                        messages,
                        temperature=0.1,
                        response_schema={"type": "json_object"},
                    )
                    parsed_response = self._parse_response(
                        llm_response.content, default_type=parsed.intent
                    )
                    trace.response_type = parsed_response.answer_type

                    # Closed tool loop: execute tools → feed results → second LLM turn
                    tool_calls = ToolLoop.parse_tool_calls_from_llm(llm_response.content)
                    max_tool_rounds = min(ToolLoop.MAX_STEPS, 2)
                    total_in = llm_response.input_tokens or 0
                    total_out = llm_response.output_tokens or 0
                    rounds = 0
                    while tool_calls and rounds < max_tool_rounds:
                        rounds += 1
                        tool_results = await self.tool_loop.execute(
                            tenant_id=tenant_id,
                            shipment_id=shipment_id,
                            tool_calls=tool_calls,
                        )
                        evidence.tool_results.extend(tool_results)
                        messages.append(
                            {"role": "assistant", "content": llm_response.content}
                        )
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "Tool results (use as evidence only; do not invent facts):\n"
                                    + json.dumps(tool_results, default=str)[:8000]
                                    + "\n\nReturn the final JSON answer now. Do not request more tools unless essential."
                                ),
                            }
                        )
                        llm_response = await llm.generate(
                            messages,
                            temperature=0.1,
                            response_schema={"type": "json_object"},
                        )
                        total_in += llm_response.input_tokens or 0
                        total_out += llm_response.output_tokens or 0
                        parsed_response = self._parse_response(
                            llm_response.content, default_type=parsed.intent
                        )
                        tool_calls = ToolLoop.parse_tool_calls_from_llm(
                            llm_response.content
                        )

                    agent_run.input_tokens = total_in
                    agent_run.output_tokens = total_out
                    agent_run.result = parsed_response.model_dump()
                except LLMError as llm_exc:
                    llm_success = False
                    llm_error_code = llm_exc.code
                    llm_retryable = llm_exc.retryable
                    llm_retry_after = llm_exc.retry_after_seconds
                    trace.add_error(llm_exc.code)
                    agent_run.error_message = llm_exc.message
                    parsed_response = build_evidence_fallback_answer(
                        evidence,
                        answer_type=parsed.intent,
                        intent=intent.value,
                        rag_freshness=rag_freshness,
                        using_stored_rag=using_stored_rag_fallback or rag_used,
                        llm_error_code=llm_exc.code,
                    )
                    trace.response_type = parsed_response.answer_type
                    evidence.warnings.append(
                        "AI synthesis temporarily unavailable; showing retrieved evidence."
                    )
            agent_run.status = "completed"
            agent_run.status = "completed"
            agent_run.latency_ms = int((time.monotonic() - start) * 1000)
            agent_run.completed_at = datetime.now(UTC)

            await self.short_memory.save(
                conversation.id,
                tenant_id,
                self.short_memory.context_from_parsed(parsed),
            )
            for key, value in self.long_memory.infer_from_message(message, parsed.to_dict()):
                await self.long_memory.remember(
                    tenant_id=tenant_id, user_id=user_id, key=key, value=value
                )

            self.db.add(
                Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=redact_pii(parsed_response.answer),
                    structured_payload={
                        **parsed_response.model_dump(),
                        "evidence_summary": {
                            "intent": intent.value,
                            "rag_source_count": len(evidence.retrieved_rag_sources),
                            "web_result_count": len(evidence.web_search_results),
                            "memory_used": bool(long_mem or evidence.short_memory),
                        },
                    },
                )
            )

            trace.data_source = data_source
            trace.current_data_verified = current_data_verified
            trace.finalize()

            payload = self._chat_payload(
                conversation_id=conversation.id,
                parsed_response=parsed_response,
                parsed=parsed,
                shipment_id=shipment_id,
                evidence=evidence,
                long_mem=long_mem,
                rag_used=rag_used,
                web_search_used=web_search_used,
                web_search_error_code=web_search_error_code,
                web_search_retryable=web_search_retryable,
                rag_freshness=rag_freshness,
                current_data_verified=current_data_verified,
                data_source=data_source,
                trace=trace,
                llm_success=llm_success,
                llm_error_code=llm_error_code,
                llm_retryable=llm_retryable,
                llm_retry_after=llm_retry_after,
            )
            # Persist research history for debugging / "which sources" follow-ups
            agent_run.result = {
                **(agent_run.result or {}),
                "research_history": {
                    "query": message,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "rag_chunks": evidence.retrieved_rag_sources[:8],
                    "web_results": evidence.web_search_results[:5],
                    "sources": payload["sources"],
                    "answer": parsed_response.answer[:4000],
                    "web_search_used": web_search_used,
                    "rag_used": rag_used,
                },
            }
            return payload
        except LLMError as llm_exc:
            llm_success = False
            llm_error_code = llm_exc.code
            trace.add_error(llm_exc.code)
            agent_run.status = "failed"
            agent_run.error_message = llm_exc.message
            parsed_response = build_evidence_fallback_answer(
                evidence,
                answer_type=parsed.intent,
                intent=intent.value,
                rag_freshness=rag_freshness,
                using_stored_rag=using_stored_rag_fallback or rag_used,
                llm_error_code=llm_exc.code,
            )
            trace.finalize()
            agent_run.status = "completed"
            return self._chat_payload(
                conversation_id=conversation.id,
                parsed_response=parsed_response,
                parsed=parsed,
                shipment_id=shipment_id,
                evidence=evidence,
                long_mem=long_mem,
                rag_used=rag_used,
                web_search_used=web_search_used,
                web_search_error_code=web_search_error_code,
                web_search_retryable=web_search_retryable,
                rag_freshness=rag_freshness,
                current_data_verified=current_data_verified,
                data_source=data_source,
                trace=trace,
                llm_success=False,
                llm_error_code=llm_error_code,
                llm_retryable=llm_exc.retryable,
                llm_retry_after=llm_exc.retry_after_seconds,
            )
        except Exception as exc:
            agent_run.status = "failed"
            agent_run.error_message = str(exc)
            trace.add_error(PipelineErrorCode.LLM_REQUEST_FAILED)
            trace.finalize()
            if rag_used or evidence.recommendations:
                parsed_response = build_evidence_fallback_answer(
                    evidence,
                    answer_type=parsed.intent,
                    intent=intent.value,
                    rag_freshness=rag_freshness,
                    using_stored_rag=using_stored_rag_fallback or rag_used,
                )
                await self.short_memory.save(
                    conversation.id,
                    tenant_id,
                    self.short_memory.context_from_parsed(parsed),
                )
                self.db.add(
                    Message(
                        conversation_id=conversation.id,
                        role="assistant",
                        content=redact_pii(parsed_response.answer),
                        structured_payload=parsed_response.model_dump(),
                    )
                )
                agent_run.status = "completed"
                agent_run.error_message = str(exc)
                return self._chat_payload(
                    conversation_id=conversation.id,
                    parsed_response=parsed_response,
                    parsed=parsed,
                    shipment_id=shipment_id,
                    evidence=evidence,
                    long_mem=long_mem,
                    rag_used=rag_used,
                    web_search_used=web_search_used,
                    web_search_error_code=web_search_error_code,
                    web_search_retryable=web_search_retryable,
                    rag_freshness=rag_freshness,
                    current_data_verified=current_data_verified,
                    data_source=data_source if data_source != "none" else "rag",
                    trace=trace,
                    llm_success=False,
                    llm_error_code=llm_error_code or PipelineErrorCode.LLM_REQUEST_FAILED,
                    llm_retryable=llm_retryable,
                    llm_retry_after=llm_retry_after,
                )
            # Prefer evidence fallback over a raw 500 when the LLM path fails
            parsed_response = build_evidence_fallback_answer(
                evidence,
                answer_type=parsed.intent,
                intent=intent.value,
                rag_freshness=rag_freshness,
                using_stored_rag=using_stored_rag_fallback or rag_used,
            )
            agent_run.status = "completed"
            return self._chat_payload(
                conversation_id=conversation.id,
                parsed_response=parsed_response,
                parsed=parsed,
                shipment_id=shipment_id,
                evidence=evidence,
                long_mem=long_mem,
                rag_used=rag_used,
                web_search_used=web_search_used,
                web_search_error_code=web_search_error_code,
                web_search_retryable=web_search_retryable,
                rag_freshness=rag_freshness,
                current_data_verified=current_data_verified,
                data_source=data_source if data_source != "none" else ("rag" if rag_used else "none"),
                trace=trace,
                llm_success=False,
                llm_error_code=llm_error_code or PipelineErrorCode.LLM_REQUEST_FAILED,
                llm_retryable=True,
                llm_retry_after=llm_retry_after,
            )

    async def _attach_shipment_context(
        self, evidence: EvidencePackage, tenant_id: uuid.UUID, shipment_id: uuid.UUID
    ) -> None:
        shipment_data = await self.shipment_tools.get_shipment(tenant_id, shipment_id)
        if not shipment_data:
            return
        evidence.shipment = shipment_data
        evidence.database_facts.append({"type": "shipment", "data": shipment_data})
        result = await self.db.execute(
            select(ShipmentIssue).where(
                ShipmentIssue.tenant_id == tenant_id,
                ShipmentIssue.shipment_id == shipment_id,
                ShipmentIssue.status == "open",
            )
        )
        evidence.open_issues = [
            {"issue_type": i.issue_type, "title": i.title, "severity": i.severity}
            for i in result.scalars().all()
        ]

    async def _fetch_live_tracking(
        self, tenant_id: uuid.UUID, shipment_id: uuid.UUID, evidence: EvidencePackage
    ) -> list[dict]:
        tracking_number = evidence.shipment.get("tracking_number")
        provider_id = evidence.shipment.get("provider_id")
        if not tracking_number or not provider_id:
            evidence.warnings.append("Tracking number or provider not set on shipment")
            return []
        tracking = await self.carrier_tools.get_tracking(
            tenant_id=tenant_id,
            shipment_id=shipment_id,
            provider_id=uuid.UUID(provider_id),
            tracking_number=tracking_number,
        )
        return [{"type": "tracking", "data": tracking}]

    def _compact_evidence_for_llm(self, evidence: EvidencePackage, *, max_chars: int = 14000) -> dict:
        """Shrink evidence so Groq free-tier TPM limits are less likely to reject the request."""

        def _trim_items(items: list, limit: int, content_len: int) -> list[dict]:
            out: list[dict] = []
            for item in items[:limit]:
                if not isinstance(item, dict):
                    continue
                row: dict = {}
                for key in (
                    "title",
                    "publisher",
                    "url",
                    "source_type",
                    "provider",
                    "freshness",
                    "label",
                    "price",
                    "price_label",
                ):
                    if item.get(key) is not None:
                        row[key] = item.get(key)
                content = (
                    item.get("content")
                    or item.get("snippet")
                    or item.get("extracted_content")
                    or item.get("excerpt")
                )
                if content:
                    row["content"] = str(content)[:content_len]
                out.append(row)
            return out

        content_len = 700
        rag_n, web_n = 5, 4
        while True:
            payload = {
                "query": evidence.query,
                "intent": evidence.intent,
                "answer_type": evidence.answer_type,
                "parsed_query": evidence.parsed_query,
                "retrieved_rag_sources": _trim_items(evidence.retrieved_rag_sources, rag_n, content_len),
                "web_search_results": _trim_items(evidence.web_search_results, web_n, content_len),
                "recommendations": evidence.recommendations[:3],
                "warnings": evidence.warnings[:5],
                "missing_information": evidence.missing_information[:5],
                "private_attachments": _trim_items(evidence.private_attachments, 2, 400),
                "tool_results": evidence.tool_results[:2],
            }
            encoded = json.dumps(payload, ensure_ascii=False, default=str)
            if len(encoded) <= max_chars or (rag_n <= 2 and web_n <= 1 and content_len <= 250):
                return payload
            if content_len > 250:
                content_len = max(250, content_len - 150)
            elif rag_n > 2:
                rag_n -= 1
            elif web_n > 1:
                web_n -= 1
            else:
                return payload

    def _labeled_evidence_sources(self, evidence: EvidencePackage) -> list[dict]:
        official = [dict(x) for x in evidence.web_search_results if x.get("tier") == "official"]
        third = [dict(x) for x in evidence.web_search_results if x.get("tier") == "third_party"]
        # Untagged web hits: validate; never default to official
        for x in evidence.web_search_results:
            if x.get("tier") in {"official", "third_party"}:
                continue
            row = dict(x)
            row["tier"] = "third_party"
            third.append(row)
        internal = []
        for x in evidence.retrieved_rag_sources:
            row = dict(x)
            row["tier"] = "internal_doc"
            row["carrier"] = row.get("carrier") or row.get("provider")
            internal.append(row)
        return assign_source_ids(
            official_web=official,
            internal_docs=internal,
            third_party_web=third,
        )

    def _build_user_prompt(self, context: AgentContext) -> str:
        labeled = self._labeled_evidence_sources(context.evidence)
        # Keep compact extras (recommendations etc.) without dumping full evidence twice
        extras = {
            "query": context.evidence.query,
            "intent": context.intent,
            "answer_type": context.evidence.answer_type,
            "parsed_query": context.evidence.parsed_query,
            "recommendations": context.evidence.recommendations[:3],
            "warnings": context.evidence.warnings[:5],
            "missing_information": context.evidence.missing_information[:5],
        }
        blocks = format_evidence_blocks(labeled)
        return f"""User message: {context.evidence.query}

Context extras:
{json.dumps(extras, ensure_ascii=False, default=str)}

{blocks}

Rules for this turn:
- Official provider/government evidence is authoritative for factual claims when it is current and applicable.
- Internal documents may be older than official web information; if they contradict official pages on price, transit, or coverage, official wins and note the internal doc may be outdated.
- Third-party information must be attributed as third-party and never framed as the carrier's own claim.
- Never invent missing values, URLs, or citations. Cite only [S#] ids present above.
- Comparison answers: side-by-side markdown table of evidence-backed dimensions only (service types, transit, coverage, COD, tracking, pricing basis, international, support). Omit or mark \"Not currently verified\" when a field lacks evidence. Never declare an absolute winner — recommend the better match for the user's stated priority with an evidence-backed tradeoff.
- Answer in the language of the question (including Roman Urdu).
- Put the formatted markdown answer in `answer`. Put source objects in `sources` using the same id/url/tier/carrier/domain/title.

Respond with JSON:
{{
  "answer": "string",
  "answer_type": "{context.evidence.answer_type}",
  "intent": "{context.intent}",
  "needs_more_information": false,
  "questions": [],
  "recommendations": [],
  "assumptions": [],
  "actions": [],
  "sources": [],
  "warnings": []
}}"""

    def _compose_sources(
        self,
        *,
        parsed_sources: list | None,
        evidence: EvidencePackage,
    ) -> list[dict]:
        labeled = self._labeled_evidence_sources(evidence)
        # Prefer labeled pipeline sources; merge any LLM-returned titles that match URLs
        by_url = {(s.get("url") or "").lower(): s for s in labeled if s.get("url")}
        for item in parsed_sources or []:
            if not isinstance(item, dict):
                continue
            url = (item.get("url") or "").lower()
            if url and url in by_url:
                if item.get("title"):
                    by_url[url]["title"] = item["title"]
        return normalize_sources(labeled, limit=12)

    def _chat_payload(
        self,
        *,
        conversation_id: uuid.UUID,
        parsed_response: StructuredAgentResponse,
        parsed,
        shipment_id: uuid.UUID | None,
        evidence: EvidencePackage,
        long_mem: dict,
        rag_used: bool,
        web_search_used: bool,
        web_search_error_code: str | None,
        web_search_retryable: bool,
        rag_freshness: str,
        current_data_verified: bool,
        data_source: str,
        trace: PipelineTrace,
        llm_success: bool,
        llm_error_code: str | None,
        llm_retryable: bool,
        llm_retry_after: float | None,
    ) -> dict:
        sources = self._compose_sources(
            parsed_sources=parsed_response.sources,
            evidence=evidence,
        )
        answer = ensure_inline_citations(parsed_response.answer, sources)
        indicator = research_indicator(
            web_search_used=web_search_used,
            rag_used=rag_used,
            source_count=len(sources),
        )
        return {
            "conversation_id": str(conversation_id),
            "answer": answer,
            "answer_type": parsed_response.answer_type,
            "intent": parsed_response.intent,
            "extracted_context": parsed.to_dict(),
            "shipment_id": str(shipment_id) if shipment_id else None,
            "recommendations": parsed_response.recommendations or evidence.recommendations,
            "assumptions": parsed_response.assumptions or evidence.missing_information,
            "actions": parsed_response.actions,
            "sources": sources,
            "warnings": list(dict.fromkeys(parsed_response.warnings + evidence.warnings)),
            "confidence": {
                "overall": "supported" if (rag_used or web_search_used or evidence.recommendations) else "limited"
            },
            "memory_used": bool(long_mem or evidence.short_memory),
            "rag_used": rag_used,
            "web_search_used": web_search_used,
            "web_search_error_code": web_search_error_code,
            "web_search_retryable": web_search_retryable,
            "live_data_used": bool(evidence.current_live_data),
            "freshness": rag_freshness,
            "current_data_verified": current_data_verified,
            "data_source": data_source,
            "research_indicator": indicator,
            "research": {
                "rag_chunk_count": len(evidence.retrieved_rag_sources),
                "web_result_count": len(evidence.web_search_results),
                "source_count": len(sources),
                "web_extracted": sum(1 for r in evidence.web_search_results if r.get("extracted")),
            },
            "internal_error_codes": trace.internal_error_codes,
            "llm_success": llm_success,
            "llm_error_code": llm_error_code,
            "retryable": llm_retryable,
            "retry_after_seconds": llm_retry_after,
        }

    async def _greeting_response(
        self,
        *,
        conversation: Conversation,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        message: str,
        shipment_id: uuid.UUID | None,
        trace: PipelineTrace,
    ) -> dict:
        """Friendly intro — no RAG / web search for simple hellos."""
        answer = (
            "Hello — I'm **Courier Guider**, your AI research desk for Pakistan courier and logistics.\n\n"
            "I can help you:\n"
            "- Compare couriers (TCS, Leopards, BlueEx, M&P, Trax, DHL, and more)\n"
            "- Understand COD, delivery times, and service policies\n"
            "- Research shipping options with cited sources\n\n"
            "Ask something like: *Compare BlueEx and TCS for COD* or *What does Leopards charge for Lahore to Karachi?*"
        )
        self.db.add(
            Message(
                conversation_id=conversation.id,
                role="user",
                content=redact_pii(message),
            )
        )
        self.db.add(
            Message(
                conversation_id=conversation.id,
                role="assistant",
                content=answer,
                structured_payload={"answer_type": "greeting", "intent": Intent.GREETING.value},
            )
        )
        await self.short_memory.save(
            conversation.id,
            tenant_id,
            {"intent": Intent.GREETING.value, "last_user_message": message[:200]},
        )
        trace.response_type = "greeting"
        trace.data_source = "none"
        trace.finalize()
        return {
            "conversation_id": str(conversation.id),
            "answer": answer,
            "answer_type": "greeting",
            "intent": Intent.GREETING.value,
            "extracted_context": {"intent": Intent.GREETING.value},
            "shipment_id": str(shipment_id) if shipment_id else None,
            "recommendations": [],
            "assumptions": [],
            "actions": [],
            "sources": [],
            "warnings": [],
            "confidence": {"overall": "supported"},
            "memory_used": False,
            "rag_used": False,
            "web_search_used": False,
            "web_search_error_code": None,
            "web_search_retryable": False,
            "live_data_used": False,
            "freshness": None,
            "current_data_verified": False,
            "data_source": "none",
            "research_indicator": None,
            "internal_error_codes": [],
            "llm_success": True,
            "llm_error_code": None,
            "retryable": False,
            "retry_after_seconds": None,
        }

    async def _get_or_create_conversation(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID | None,
        shipment_id: uuid.UUID | None,
        message: str,
    ) -> Conversation:
        if conversation_id:
            result = await self.db.execute(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.tenant_id == tenant_id,
                )
            )
            conv = result.scalar_one_or_none()
            if conv:
                return conv

        conv = Conversation(tenant_id=tenant_id, user_id=user_id, shipment_id=shipment_id, title=message[:80])
        self.db.add(conv)
        await self.db.flush()
        return conv

    def _parse_response(self, content: str, default_type: str = "general_answer") -> StructuredAgentResponse:
        cleaned = CourierGuiderAgent._strip_llm_noise(content)
        payload = CourierGuiderAgent._extract_json_object(cleaned)
        if payload is not None:
            try:
                # Some models nest the answer as a JSON string
                if isinstance(payload.get("answer"), str):
                    payload["answer"] = CourierGuiderAgent._normalize_answer_text(payload["answer"])
                parsed = StructuredAgentResponse.model_validate(payload)
                if parsed.answer_type == "general_answer" and default_type != "general_answer":
                    parsed.answer_type = default_type
                # Drop parse-fallback noise if we recovered a real answer
                parsed.warnings = [
                    w for w in parsed.warnings if w != "Unstructured LLM response"
                ]
                if parsed.answer.strip():
                    return parsed
            except Exception:
                # Fall through to softer recovery
                answer = payload.get("answer")
                if isinstance(answer, str) and answer.strip():
                    return StructuredAgentResponse(
                        answer=CourierGuiderAgent._normalize_answer_text(answer),
                        answer_type=str(payload.get("answer_type") or default_type),
                        intent=str(payload.get("intent") or "other"),
                        recommendations=list(payload.get("recommendations") or []),
                        assumptions=list(payload.get("assumptions") or []),
                        actions=list(payload.get("actions") or []),
                        sources=list(payload.get("sources") or []),
                        warnings=[],
                    )

        # Model returned markdown / prose instead of JSON
        prose = CourierGuiderAgent._normalize_answer_text(cleaned)
        if prose.strip().startswith("{") and '"answer"' in prose:
            # Last-chance: pull answer string with a tolerant regex
            match = re.search(
                r'"answer"\s*:\s*"((?:\\.|[^"\\])*)"',
                prose,
                flags=re.DOTALL,
            )
            if match:
                raw_answer = match.group(1)
                recovered = CourierGuiderAgent._normalize_answer_text(
                    raw_answer.replace("\\n", "\n")
                    .replace("\\t", "\t")
                    .replace('\\"', '"')
                )
                if recovered.strip():
                    return StructuredAgentResponse(
                        answer=recovered,
                        answer_type=default_type,
                        intent="other",
                        warnings=[],
                    )

        return StructuredAgentResponse(
            answer=prose,
            answer_type=default_type,
            intent="other",
            warnings=[],
        )

    @staticmethod
    def _strip_llm_noise(content: str) -> str:
        text = (content or "").strip()
        text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"<thinking>[\s\S]*?</thinking>", "", text, flags=re.IGNORECASE)
        text = re.sub(r"```(?:json|JSON)?\s*", "", text)
        text = text.replace("```", "")
        return text.strip()

    @staticmethod
    def _normalize_answer_text(text: str) -> str:
        value = (text or "").strip()
        if not value:
            return value
        # Unwrap accidental quoted JSON string
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            inner = value[1:-1]
            if "\\n" in inner or "##" in inner or "**" in inner:
                value = inner
        # Turn escaped newlines into real markdown line breaks
        if value.count("\\n") >= 2 and value.count("\\n") > value.count("\n"):
            value = (
                value.replace("\\n", "\n")
                .replace("\\t", "\t")
                .replace('\\"', '"')
                .replace("\\'", "'")
            )
        return value.strip()

    @staticmethod
    def _extract_json_object(content: str) -> dict | None:
        text = (content or "").strip()
        if not text:
            return None
        # Direct parse
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
            if isinstance(data, str):
                nested = json.loads(data)
                if isinstance(nested, dict):
                    return nested
        except Exception:
            pass
        # Largest {...} slice
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        blob = text[start : end + 1]
        try:
            data = json.loads(blob)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        # Repair common model mistakes: trailing commas
        repaired = re.sub(r",\s*([}\]])", r"\1", blob)
        try:
            data = json.loads(repaired)
            if isinstance(data, dict):
                return data
        except Exception:
            return None
        return None
