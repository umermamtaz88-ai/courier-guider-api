"""Courier Guider schema additions."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002_courier_guider"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge_sources", sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True))
    op.add_column("knowledge_sources", sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shipments", sa.Column("tracking_number", sa.String(length=100), nullable=True))
    op.add_column("agent_runs", sa.Column("prompt_version", sa.String(length=50), nullable=True))

    op.create_table(
        "provider_capabilities",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider_id", sa.UUID(), nullable=False),
        sa.Column("tracking", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("live_quote", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("availability", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("delivery_estimate", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("booking", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("returns", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("claims", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("settlements", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("webhooks", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_id"),
    )

    op.create_table(
        "live_data_snapshots",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("shipment_id", sa.UUID(), nullable=False),
        sa.Column("provider_id", sa.UUID(), nullable=False),
        sa.Column("data_type", sa.String(length=50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["provider_id"], ["providers.id"]),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_live_data_shipment_type", "live_data_snapshots", ["shipment_id", "data_type"])


def downgrade() -> None:
    op.drop_index("ix_live_data_shipment_type", table_name="live_data_snapshots")
    op.drop_table("live_data_snapshots")
    op.drop_table("provider_capabilities")
    op.drop_column("agent_runs", "prompt_version")
    op.drop_column("shipments", "tracking_number")
    op.drop_column("knowledge_sources", "effective_to")
    op.drop_column("knowledge_sources", "effective_from")
