import re
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel


class RetrievalFilters(BaseModel):
    tenant_id: uuid.UUID
    shipment_id: uuid.UUID | None = None
    provider_id: uuid.UUID | None = None
    country: str | None = None
    destination_country: str | None = None
    direction: str | None = None
    policy_type: str | None = None
    jurisdiction: str | None = None
    as_of: datetime | None = None


def build_scope_filter(filters: RetrievalFilters):
    from sqlalchemy import and_, or_

    from app.db.models import KnowledgeScope, KnowledgeSource

    scope_filter = or_(
        KnowledgeSource.scope_type == KnowledgeScope.GLOBAL,
        and_(
            KnowledgeSource.scope_type == KnowledgeScope.TENANT,
            KnowledgeSource.scope_id == filters.tenant_id,
        ),
    )
    if filters.shipment_id:
        scope_filter = or_(
            scope_filter,
            and_(
                KnowledgeSource.scope_type == KnowledgeScope.SHIPMENT,
                KnowledgeSource.scope_id == filters.shipment_id,
            ),
        )
    return scope_filter


def extract_query_entities(query: str) -> dict:
    entities: dict = {}
    if match := re.search(r"\b(\d+(?:\.\d+)?)\s*kg\b", query, re.I):
        entities["weight_kg"] = float(match.group(1))
    for country in ("Pakistan", "UAE", "Dubai", "Lahore", "Karachi"):
        if country.lower() in query.lower():
            entities.setdefault("locations", []).append(country)
    if re.search(r"\b(return|refund|claim|cod|customs|document)\b", query, re.I):
        entities["topics"] = re.findall(r"\b(return|refund|claim|cod|customs|document\w*)\b", query, re.I)
    return entities
