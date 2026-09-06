import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    password: str = Field(min_length=8)
    tenant_name: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    tenant_id: uuid.UUID | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    tenant_id: uuid.UUID | None = None


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str

    model_config = {"from_attributes": True}


class TenantCreate(BaseModel):
    name: str


class TenantResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: str

    model_config = {"from_attributes": True}


class ShipmentItemCreate(BaseModel):
    description: str
    category: str | None = None
    quantity: int = 1
    weight: float | None = None
    hs_code: str | None = None


class ShipmentCreate(BaseModel):
    reference_code: str | None = None
    direction: str = "export"
    service_type: str = "courier"
    origin_country: str | None = None
    origin_city: str | None = None
    destination_country: str | None = None
    destination_city: str | None = None
    total_weight: float | None = None
    weight_unit: str = "kg"
    declared_value: float | None = None
    declared_currency: str | None = None
    cod_enabled: bool = False
    items: list[ShipmentItemCreate] = Field(default_factory=list)


class ShipmentResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    reference_code: str
    direction: str
    service_type: str
    status: str
    origin_country: str | None
    origin_city: str | None
    destination_country: str | None
    destination_city: str | None
    total_weight: float | None
    weight_unit: str
    declared_value: float | None
    declared_currency: str | None
    cod_enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID | None = None
    shipment_id: uuid.UUID | None = None
    message: str
    preferences: dict[str, Any] = Field(default_factory=dict)


class Source(BaseModel):
    id: str | None = None
    title: str
    url: str | None = None
    domain: str | None = None
    carrier: str | None = None
    tier: Literal["official", "third_party", "internal_doc"] | None = None
    publisher: str | None = None
    provider: str | None = None
    source_type: str | None = None
    published_at: str | None = None
    effective_date: str | None = None
    retrieved_at: str | None = None
    authority_score: float | None = None
    freshness_status: str | None = None
    freshness: str | None = None
    page: int | None = None
    date: str | None = None
    relevance: str | None = None
    authority_level: float | None = None
    content: str | None = None
    label: str | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    answer_type: str = "general_answer"
    intent: str
    extracted_context: dict[str, Any] = Field(default_factory=dict)
    shipment_id: str | None = None
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: dict[str, str] = Field(default_factory=dict)
    memory_used: bool = False
    rag_used: bool = False
    web_search_used: bool = False
    live_data_used: bool = False
    freshness: str | None = None
    current_data_verified: bool = False
    data_source: str = "none"
    internal_error_codes: list[str] = Field(default_factory=list)
    llm_success: bool = True
    llm_error_code: str | None = None
    web_search_error_code: str | None = None
    web_search_retryable: bool = False
    retryable: bool = False
    retry_after_seconds: float | None = None


class KnowledgeIngestRequest(BaseModel):
    title: str
    text: str
    scope_type: str = "GLOBAL"
    scope_id: uuid.UUID | None = None
    source_type: str = "uploaded"
    publisher: str | None = None
    authority_level: int = 3
