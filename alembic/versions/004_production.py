"""Production upgrade — orders, NDR, COD, policies."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004_production"
down_revision: Union[str, None] = "003_complete"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("external_customer_id", sa.String(100)),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255)),
        sa.Column("phone", sa.String(50)),
        sa.Column("default_address", sa.JSON()),
        sa.Column("metadata", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customers_tenant_id", "customers", ["tenant_id"])

    op.create_table(
        "addresses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("raw_address", sa.Text(), nullable=False),
        sa.Column("normalized_address", sa.Text()),
        sa.Column("city", sa.String(100)),
        sa.Column("province", sa.String(100)),
        sa.Column("country", sa.String(100)),
        sa.Column("postal_code", sa.String(20)),
        sa.Column("latitude", sa.Numeric(10, 7)),
        sa.Column("longitude", sa.Numeric(10, 7)),
        sa.Column("validation_status", sa.String(30)),
        sa.Column("validation_source", sa.String(50)),
        sa.Column("confidence", sa.Numeric(4, 3)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("external_order_id", sa.String(100)),
        sa.Column("platform", sa.String(50)),
        sa.Column("customer_id", sa.UUID()),
        sa.Column("status", sa.Enum("pending", "confirmed", "fulfilled", "cancelled", name="orderstatus")),
        sa.Column("payment_status", sa.String(30)),
        sa.Column("fulfillment_status", sa.String(30)),
        sa.Column("currency", sa.String(10)),
        sa.Column("subtotal", sa.Numeric(12, 2)),
        sa.Column("shipping_amount", sa.Numeric(12, 2)),
        sa.Column("discount_amount", sa.Numeric(12, 2)),
        sa.Column("tax_amount", sa.Numeric(12, 2)),
        sa.Column("total_amount", sa.Numeric(12, 2)),
        sa.Column("shipping_address", sa.JSON()),
        sa.Column("billing_address", sa.JSON()),
        sa.Column("metadata", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orders_tenant_external", "orders", ["tenant_id", "external_order_id"])

    op.create_table(
        "order_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("sku", sa.String(100)),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("quantity", sa.Integer()),
        sa.Column("unit_price", sa.Numeric(12, 2)),
        sa.Column("weight", sa.Numeric(10, 3)),
        sa.Column("dimensions", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "order_shipment_links",
        sa.Column("order_id", sa.UUID(), nullable=False),
        sa.Column("shipment_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"]),
        sa.PrimaryKeyConstraint("order_id", "shipment_id"),
    )

    op.create_table(
        "delivery_exceptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("shipment_id", sa.UUID(), nullable=False),
        sa.Column("provider_id", sa.UUID()),
        sa.Column("reason_code", sa.String(50), nullable=False),
        sa.Column("reason_text", sa.Text()),
        sa.Column("attempt_number", sa.Integer()),
        sa.Column("event_time", sa.DateTime(timezone=True)),
        sa.Column("next_action", sa.String(100)),
        sa.Column("customer_contact_status", sa.String(30)),
        sa.Column("resolution_status", sa.String(30)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"]),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "pickups",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("shipment_id", sa.UUID(), nullable=False),
        sa.Column("provider_id", sa.UUID()),
        sa.Column("pickup_address", sa.JSON()),
        sa.Column("requested_at", sa.DateTime(timezone=True)),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(30)),
        sa.Column("provider_reference", sa.String(100)),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"]),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "cod_reconciliations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("shipment_id", sa.UUID(), nullable=False),
        sa.Column("order_expected", sa.Numeric(12, 2)),
        sa.Column("shipment_cod_amount", sa.Numeric(12, 2)),
        sa.Column("provider_collected", sa.Numeric(12, 2)),
        sa.Column("provider_settled", sa.Numeric(12, 2)),
        sa.Column("company_received", sa.Numeric(12, 2)),
        sa.Column("currency", sa.String(10)),
        sa.Column("discrepancy", sa.Numeric(12, 2)),
        sa.Column("status", sa.String(30)),
        sa.Column("discrepancy_type", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "tenant_policies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("preferred_providers", sa.JSON()),
        sa.Column("max_shipping_cost", sa.Numeric(12, 2)),
        sa.Column("max_delivery_days", sa.Integer()),
        sa.Column("return_policy_text", sa.Text()),
        sa.Column("refund_policy_text", sa.Text()),
        sa.Column("cod_threshold", sa.Numeric(12, 2)),
        sa.Column("high_value_threshold", sa.Numeric(12, 2)),
        sa.Column("restricted_products", sa.JSON()),
        sa.Column("default_pickup_location", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id"),
    )

    op.create_table(
        "quote_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("shipment_id", sa.UUID(), nullable=False),
        sa.Column("provider_id", sa.UUID(), nullable=False),
        sa.Column("service_id", sa.UUID()),
        sa.Column("breakdown", sa.JSON(), nullable=False),
        sa.Column("assumptions", sa.JSON()),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("currency", sa.String(10)),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["provider_services.id"]),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "volumetric_weight_rules",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider_id", sa.UUID()),
        sa.Column("service_id", sa.UUID()),
        sa.Column("origin_country", sa.String(100)),
        sa.Column("destination_country", sa.String(100)),
        sa.Column("divisor", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True)),
        sa.Column("source_url", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["provider_services.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "escalations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("shipment_id", sa.UUID()),
        sa.Column("conversation_id", sa.UUID()),
        sa.Column("reason", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(20)),
        sa.Column("assigned_to", sa.UUID()),
        sa.Column("status", sa.String(30)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "rag_feedback",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID()),
        sa.Column("conversation_id", sa.UUID()),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text()),
        sa.Column("source_ids", sa.JSON()),
        sa.Column("feedback_type", sa.String(30), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "integration_health",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("integration_type", sa.String(50), nullable=False),
        sa.Column("integration_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30)),
        sa.Column("failure_count", sa.Integer()),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_message", sa.Text()),
        sa.Column("circuit_open", sa.Boolean()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("operation", sa.String(100), nullable=False),
        sa.Column("response", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "key", "operation"),
    )


def downgrade() -> None:
    for table in (
        "idempotency_keys", "integration_health", "rag_feedback", "escalations",
        "volumetric_weight_rules", "quote_snapshots", "tenant_policies",
        "cod_reconciliations", "pickups", "delivery_exceptions",
        "order_shipment_links", "order_items", "orders", "addresses", "customers",
    ):
        op.drop_table(table)
    op.execute("DROP TYPE IF EXISTS orderstatus")
