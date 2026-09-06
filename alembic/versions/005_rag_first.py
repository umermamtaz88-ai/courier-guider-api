"""RAG-first rebuild — memory tables and chunk full-text search."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005_rag_first"
down_revision: Union[str, None] = "004_production"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversation_contexts",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("conversation_id"),
    )

    op.create_table(
        "user_memories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("memory_key", sa.String(100), nullable=False),
        sa.Column("memory_value", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(50)),
        sa.Column("confidence", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "user_id", "memory_key"),
    )
    op.create_index("ix_user_memories_tenant_user", "user_memories", ["tenant_id", "user_id"])

    op.add_column(
        "knowledge_chunks",
        sa.Column("search_vector", sa.dialects.postgresql.TSVECTOR(), nullable=True),
    )
    op.execute(
        """
        UPDATE knowledge_chunks
        SET search_vector = to_tsvector('english', coalesce(content, ''))
        """
    )
    op.create_index(
        "ix_knowledge_chunks_search_vector",
        "knowledge_chunks",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_chunks_search_vector", table_name="knowledge_chunks")
    op.drop_column("knowledge_chunks", "search_vector")
    op.drop_table("user_memories")
    op.drop_table("conversation_contexts")
