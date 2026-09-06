import json
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.tools.carrier_tools import CarrierTools
from app.ai.tools.document_tools import DocumentTools
from app.ai.tools.rag_tools import RAGTools
from app.ai.tools.registry import TOOL_REGISTRY, Permission
from app.ai.tools.shipment_tools import ShipmentTools
from app.ai.tools.web_tools import WebTools


class ToolLoop:
    """Execute read-only tool calls requested by the agent (max steps)."""

    MAX_STEPS = 4

    def __init__(self, db: AsyncSession):
        self.db = db
        self.shipment_tools = ShipmentTools(db)
        self.rag_tools = RAGTools(db)
        self.carrier_tools = CarrierTools(db)
        self.document_tools = DocumentTools(db)
        self.web_tools = WebTools(db)

    async def execute(
        self,
        *,
        tenant_id: uuid.UUID,
        shipment_id: uuid.UUID | None,
        tool_calls: list[dict[str, Any]],
        allowed_permissions: set[Permission] | None = None,
    ) -> list[dict[str, Any]]:
        allowed_permissions = allowed_permissions or {Permission.READ}
        results: list[dict[str, Any]] = []

        for call in tool_calls[: self.MAX_STEPS]:
            name = call.get("tool") or call.get("name")
            args = call.get("args") or call.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            if not name or name not in TOOL_REGISTRY:
                results.append({"tool": name, "error": "unknown_tool"})
                continue
            if TOOL_REGISTRY[name] not in allowed_permissions:
                results.append({"tool": name, "error": "permission_denied"})
                continue

            try:
                result = await self._dispatch(name, tenant_id, shipment_id, args)
                results.append({"tool": name, "result": result})
            except Exception as exc:
                results.append({"tool": name, "error": str(exc)[:300]})

        return results

    async def _dispatch(
        self,
        name: str,
        tenant_id: uuid.UUID,
        shipment_id: uuid.UUID | None,
        args: dict[str, Any],
    ) -> Any:
        if name == "get_shipment":
            sid = uuid.UUID(args["shipment_id"]) if args.get("shipment_id") else shipment_id
            if sid is None:
                return {"error": "shipment_id_required"}
            return await self.shipment_tools.get_shipment(tenant_id, sid)

        if name == "search_knowledge":
            return await self.rag_tools.search_knowledge(
                args.get("query", ""),
                tenant_id=tenant_id,
                shipment_id=shipment_id,
            )

        if name == "search_web":
            providers = args.get("providers")
            if isinstance(providers, str):
                providers = [providers]
            return await self.web_tools.search_web(
                args.get("query", ""),
                tenant_id=tenant_id,
                providers=providers,
                max_results=int(args.get("max_results") or 5),
            )

        if name == "get_documents" and shipment_id:
            return await self.document_tools.get_documents(tenant_id, shipment_id)

        if name == "get_tracking" and shipment_id:
            return await self.carrier_tools.get_tracking(
                tenant_id=tenant_id,
                shipment_id=shipment_id,
                provider_id=uuid.UUID(args["provider_id"]),
                tracking_number=args["tracking_number"],
            )

        return {"error": f"tool_not_implemented:{name}"}

    @staticmethod
    def parse_tool_calls_from_llm(content: str) -> list[dict[str, Any]]:
        try:
            start = content.find("{")
            end = content.rfind("}") + 1
            if start < 0 or end <= start:
                return []
            payload = json.loads(content[start:end])
            calls = payload.get("tool_calls") or payload.get("actions") or []
            return [c for c in calls if isinstance(c, dict) and (c.get("tool") or c.get("name"))]
        except Exception:
            return []
