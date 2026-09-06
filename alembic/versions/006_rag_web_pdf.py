"""RAG upgrade — crawl history, versions, web search cache, attachments."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006_rag_web_pdf"
down_revision: Union[str, None] = "005_rag_first"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("knowledge_sources", sa.Column("domain", sa.String(255), nullable=True))
    op.add_column("knowledge_sources", sa.Column("base_url", sa.String(500), nullable=True))
    op.add_column("knowledge_sources", sa.Column("country", sa.String(100), nullable=True))
    op.add_column("knowledge_sources", sa.Column("crawl_enabled", sa.Boolean(), server_default="false"))
    op.add_column("knowledge_sources", sa.Column("search_enabled", sa.Boolean(), server_default="true"))
    op.add_column("knowledge_sources", sa.Column("persist_to_rag", sa.Boolean(), server_default="true"))
    op.add_column("knowledge_sources", sa.Column("refresh_frequency_hours", sa.Integer(), server_default="168"))
    op.add_column("knowledge_sources", sa.Column("last_crawled_at", sa.DateTime(timezone=True)))
    op.add_column("knowledge_sources", sa.Column("last_changed_at", sa.DateTime(timezone=True)))
    op.add_column("knowledge_sources", sa.Column("last_success_at", sa.DateTime(timezone=True)))
    op.add_column("knowledge_sources", sa.Column("last_error", sa.Text()))

    op.add_column("knowledge_chunks", sa.Column("version_id", sa.UUID(), nullable=True))
    op.add_column(
        "knowledge_chunks",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_table(
        "knowledge_source_urls",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("allowed", sa.Boolean(), server_default="true"),
        sa.Column("priority", sa.Integer(), server_default="1"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("last_content_hash", sa.String(64)),
        sa.Column("last_crawled_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(30), server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "crawl_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(30), server_default="running"),
        sa.Column("pages_found", sa.Integer(), server_default="0"),
        sa.Column("pages_changed", sa.Integer(), server_default="0"),
        sa.Column("pages_added", sa.Integer(), server_default="0"),
        sa.Column("pages_failed", sa.Integer(), server_default="0"),
        sa.Column("error", sa.Text()),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "knowledge_document_versions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("raw_content", sa.Text()),
        sa.Column("clean_content", sa.Text()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("effective_from", sa.DateTime(timezone=True)),
        sa.Column("effective_to", sa.DateTime(timezone=True)),
        sa.Column("crawled_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(30), server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "knowledge_change_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID()),
        sa.Column("old_version_id", sa.UUID()),
        sa.Column("new_version_id", sa.UUID()),
        sa.Column("change_summary", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["source_id"], ["knowledge_sources.id"]),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "web_search_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID()),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("normalized_query", sa.String(500), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("url", sa.String(1000)),
        sa.Column("title", sa.String(500)),
        sa.Column("snippet", sa.Text()),
        sa.Column("content", sa.Text()),
        sa.Column("authority_level", sa.Integer()),
        sa.Column("source_type", sa.String(50)),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("persisted_to_rag", sa.Boolean(), server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_web_search_norm_query", "web_search_results", ["normalized_query"])

    op.create_table(
        "chat_attachments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID()),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(100)),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("sha256_hash", sa.String(64)),
        sa.Column("scope", sa.String(30), server_default="PRIVATE_USER"),
        sa.Column("processing_status", sa.String(30), server_default="uploaded"),
        sa.Column("extracted_text", sa.Text()),
        sa.Column("extraction_metadata", sa.JSON()),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("chat_attachments")
    op.drop_index("ix_web_search_norm_query", table_name="web_search_results")
    op.drop_table("web_search_results")
    op.drop_table("knowledge_change_events")
    op.drop_table("knowledge_document_versions")
    op.drop_table("crawl_runs")
    op.drop_table("knowledge_source_urls")
    op.drop_column("knowledge_chunks", "updated_at")
    op.drop_column("knowledge_chunks", "version_id")
    for col in (
        "last_error", "last_success_at", "last_changed_at", "last_crawled_at",
        "refresh_frequency_hours", "persist_to_rag", "search_enabled", "crawl_enabled",
        "country", "base_url", "domain",
    ):
        op.drop_column("knowledge_sources", col)
