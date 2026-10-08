"""PDF uploads: new ingestion job kind and an optional display name.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ingestion_jobs", sa.Column("display_name", sa.String(300), nullable=True))
    op.drop_constraint("ck_ingestion_jobs_kind", "ingestion_jobs", type_="check")
    op.create_check_constraint(
        "ck_ingestion_jobs_kind", "ingestion_jobs", "kind IN ('arxiv_import', 'pdf_upload')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM ingestion_jobs WHERE kind = 'pdf_upload'")
    op.drop_constraint("ck_ingestion_jobs_kind", "ingestion_jobs", type_="check")
    op.create_check_constraint(
        "ck_ingestion_jobs_kind", "ingestion_jobs", "kind IN ('arxiv_import')"
    )
    op.drop_column("ingestion_jobs", "display_name")
