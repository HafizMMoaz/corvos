"""Add Corvos docs tables for global documentation storage

Revision ID: 60
Revises: 59
"""

from collections.abc import Sequence

from alembic import op
from app.config import config

# revision identifiers, used by Alembic.
revision: str = "60"
down_revision: str | None = "59"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Get embedding dimension from config
EMBEDDING_DIM = config.embedding_model_instance.dimension


def upgrade() -> None:
    """Create corvos_docs_documents and corvos_docs_chunks tables."""

    # Create corvos_docs_documents table
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'corvos_docs_documents'
            ) THEN
                CREATE TABLE corvos_docs_documents (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    source VARCHAR NOT NULL UNIQUE,
                    title VARCHAR NOT NULL,
                    content TEXT NOT NULL,
                    content_hash VARCHAR NOT NULL,
                    embedding vector({EMBEDDING_DIM}),
                    updated_at TIMESTAMP WITH TIME ZONE
                );
            END IF;
        END$$;
        """
    )

    # Create indexes for corvos_docs_documents
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'corvos_docs_documents' AND indexname = 'ix_corvos_docs_documents_source'
            ) THEN
                CREATE INDEX ix_corvos_docs_documents_source ON corvos_docs_documents(source);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'corvos_docs_documents' AND indexname = 'ix_corvos_docs_documents_content_hash'
            ) THEN
                CREATE INDEX ix_corvos_docs_documents_content_hash ON corvos_docs_documents(content_hash);
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'corvos_docs_documents' AND indexname = 'ix_corvos_docs_documents_updated_at'
            ) THEN
                CREATE INDEX ix_corvos_docs_documents_updated_at ON corvos_docs_documents(updated_at);
            END IF;
        END$$;
        """
    )

    # Create corvos_docs_chunks table
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'corvos_docs_chunks'
            ) THEN
                CREATE TABLE corvos_docs_chunks (
                    id SERIAL PRIMARY KEY,
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                    content TEXT NOT NULL,
                    embedding vector({EMBEDDING_DIM}),
                    document_id INTEGER NOT NULL REFERENCES corvos_docs_documents(id) ON DELETE CASCADE
                );
            END IF;
        END$$;
        """
    )

    # Create indexes for corvos_docs_chunks
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes
                WHERE tablename = 'corvos_docs_chunks' AND indexname = 'ix_corvos_docs_chunks_document_id'
            ) THEN
                CREATE INDEX ix_corvos_docs_chunks_document_id ON corvos_docs_chunks(document_id);
            END IF;
        END$$;
        """
    )

    # Create vector indexes for similarity search
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS corvos_docs_documents_vector_index 
        ON corvos_docs_documents USING hnsw (embedding public.vector_cosine_ops);
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS corvos_docs_chunks_vector_index 
        ON corvos_docs_chunks USING hnsw (embedding public.vector_cosine_ops);
        """
    )

    # Create full-text search indexes (same pattern as documents/chunks tables)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS corvos_docs_documents_search_index 
        ON corvos_docs_documents USING gin (to_tsvector('english', content));
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS corvos_docs_chunks_search_index 
        ON corvos_docs_chunks USING gin (to_tsvector('english', content));
        """
    )


def downgrade() -> None:
    """Remove corvos docs tables."""
    # Drop full-text search indexes
    op.execute("DROP INDEX IF EXISTS corvos_docs_chunks_search_index")
    op.execute("DROP INDEX IF EXISTS corvos_docs_documents_search_index")

    # Drop vector indexes
    op.execute("DROP INDEX IF EXISTS corvos_docs_chunks_vector_index")
    op.execute("DROP INDEX IF EXISTS corvos_docs_documents_vector_index")

    # Drop regular indexes
    op.execute("DROP INDEX IF EXISTS ix_corvos_docs_chunks_document_id")
    op.execute("DROP INDEX IF EXISTS ix_corvos_docs_documents_updated_at")
    op.execute("DROP INDEX IF EXISTS ix_corvos_docs_documents_content_hash")
    op.execute("DROP INDEX IF EXISTS ix_corvos_docs_documents_source")

    # Drop tables (chunks first due to FK)
    op.execute("DROP TABLE IF EXISTS corvos_docs_chunks")
    op.execute("DROP TABLE IF EXISTS corvos_docs_documents")
