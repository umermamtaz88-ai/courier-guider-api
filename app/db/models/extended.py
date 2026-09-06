"""Extended production models — orders, NDR, COD, policies."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, new_uuid


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    external_customer_id: Mapped[str | None] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    default_address: Mapped[dict | None] = mapped_column(JSONB)
    customer_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB)


class Address(Base, TimestampMixin):
    __tablename__ = "addresses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    raw_address: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(100))
    province: Mapped[str | None] = mapped_column(String(100))
    country: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    latitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[float | None] = mapped_column(Numeric(10, 7))
    validation_status: Mapped[str] = mapped_column(String(30), default="unvalidated")
    validation_source: Mapped[str | None] = mapped_column(String(50))
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))


class Order(Base, TimestampMixin):
    __tablename__ = "orders"
    __table_args__ = (Index("ix_orders_tenant_external", "tenant_id", "external_order_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    external_order_id: Mapped[str | None] = mapped_column(String(100))
    platform: Mapped[str] = mapped_column(String(50), default="manual")
    customer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("customers.id"))
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, values_callable=lambda statuses: [status.value for status in statuses]),
        default=OrderStatus.PENDING,
    )
    payment_status: Mapped[str] = mapped_column(String(30), default="pending")
    fulfillment_status: Mapped[str] = mapped_column(String(30), default="unfulfilled")
    currency: Mapped[str] = mapped_column(String(10), default="PKR")
    subtotal: Mapped[float | None] = mapped_column(Numeric(12, 2))
    shipping_amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    discount_amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    tax_amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    total_amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    shipping_address: Mapped[dict | None] = mapped_column(JSONB)
    billing_address: Mapped[dict | None] = mapped_column(JSONB)
    order_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB)

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")


class OrderItem(Base, TimestampMixin):
    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    weight: Mapped[float | None] = mapped_column(Numeric(10, 3))
    dimensions: Mapped[dict | None] = mapped_column(JSONB)

    order: Mapped["Order"] = relationship(back_populates="items")


class OrderShipmentLink(Base):
    __tablename__ = "order_shipment_links"

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), primary_key=True)
    shipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shipments.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DeliveryException(Base, TimestampMixin):
    __tablename__ = "delivery_exceptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    shipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shipments.id"), nullable=False)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("providers.id"))
    reason_code: Mapped[str] = mapped_column(String(50), nullable=False)
    reason_text: Mapped[str | None] = mapped_column(Text)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    next_action: Mapped[str | None] = mapped_column(String(100))
    customer_contact_status: Mapped[str] = mapped_column(String(30), default="not_contacted")
    resolution_status: Mapped[str] = mapped_column(String(30), default="ndr_open")


class Pickup(Base, TimestampMixin):
    __tablename__ = "pickups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    shipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shipments.id"), nullable=False)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("providers.id"))
    pickup_address: Mapped[dict | None] = mapped_column(JSONB)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="requested")
    provider_reference: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)


class CodReconciliation(Base, TimestampMixin):
    __tablename__ = "cod_reconciliations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    shipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shipments.id"), nullable=False)
    order_expected: Mapped[float | None] = mapped_column(Numeric(12, 2))
    shipment_cod_amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    provider_collected: Mapped[float | None] = mapped_column(Numeric(12, 2))
    provider_settled: Mapped[float | None] = mapped_column(Numeric(12, 2))
    company_received: Mapped[float | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(10), default="PKR")
    discrepancy: Mapped[float | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(30), default="pending")
    discrepancy_type: Mapped[str | None] = mapped_column(String(50))


class TenantPolicy(Base, TimestampMixin):
    __tablename__ = "tenant_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), unique=True, nullable=False)
    preferred_providers: Mapped[list | None] = mapped_column(JSONB)
    max_shipping_cost: Mapped[float | None] = mapped_column(Numeric(12, 2))
    max_delivery_days: Mapped[int | None] = mapped_column(Integer)
    return_policy_text: Mapped[str | None] = mapped_column(Text)
    refund_policy_text: Mapped[str | None] = mapped_column(Text)
    cod_threshold: Mapped[float | None] = mapped_column(Numeric(12, 2))
    high_value_threshold: Mapped[float | None] = mapped_column(Numeric(12, 2))
    restricted_products: Mapped[list | None] = mapped_column(JSONB)
    default_pickup_location: Mapped[dict | None] = mapped_column(JSONB)


class QuoteSnapshot(Base):
    __tablename__ = "quote_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    shipment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("shipments.id"), nullable=False)
    provider_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("providers.id"), nullable=False)
    service_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("provider_services.id"))
    breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False)
    assumptions: Mapped[dict | None] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="PKR")
    total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class VolumetricWeightRule(Base, TimestampMixin):
    __tablename__ = "volumetric_weight_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("providers.id"))
    service_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("provider_services.id"))
    origin_country: Mapped[str | None] = mapped_column(String(100))
    destination_country: Mapped[str | None] = mapped_column(String(100))
    divisor: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_url: Mapped[str | None] = mapped_column(String(500))


class Escalation(Base, TimestampMixin):
    __tablename__ = "escalations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    shipment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("shipments.id"))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("conversations.id"))
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(30), default="open")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RagFeedback(Base):
    __tablename__ = "rag_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("conversations.id"))
    query: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    source_ids: Mapped[list | None] = mapped_column(JSONB)
    feedback_type: Mapped[str] = mapped_column(String(30), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IntegrationHealth(Base, TimestampMixin):
    __tablename__ = "integration_health"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    integration_type: Mapped[str] = mapped_column(String(50), nullable=False)
    integration_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="healthy")
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_message: Mapped[str | None] = mapped_column(Text)
    circuit_open: Mapped[bool] = mapped_column(Boolean, default=False)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("tenant_id", "key", "operation"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    operation: Mapped[str] = mapped_column(String(100), nullable=False)
    response: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
