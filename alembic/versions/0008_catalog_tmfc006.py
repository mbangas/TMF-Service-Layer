"""catalog_tmfc006_extensions

Revision ID: 0008_catalog_tmfc006
Revises: 0007_testing_initial
Create Date: 2026-03-07 00:00:00.000000

Adds tables for TMFC006 full Service Catalog Management compliance (TMF633):
  - service_category           (hierarchical categories)
  - service_candidate          (links ServiceSpecification to categories)
  - service_catalog            (top-level catalog container)
  - service_catalog_category   (M2M: ServiceCatalog ↔ ServiceCategory)
  - service_candidate_category (M2M: ServiceCandidate ↔ ServiceCategory)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_catalog_tmfc006"
down_revision: Union[str, None] = "0007_testing_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create TMFC006 catalog extension tables."""

    # ── service_category ──────────────────────────────────────────────────────
    op.create_table(
        "service_category",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("href", sa.String(512), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(32), nullable=True),
        sa.Column(
            "lifecycle_status",
            sa.String(32),
            nullable=False,
            server_default="active",
        ),
        sa.Column("is_root", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("parent_id", sa.String(36), nullable=True),
        sa.Column("last_update", sa.String(64), nullable=True),
        sa.Column("type", sa.String(128), nullable=True),
        sa.Column("base_type", sa.String(128), nullable=True),
        sa.Column("schema_location", sa.String(512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["service_category.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_service_category_name", "service_category", ["name"])
    op.create_index(
        "ix_service_category_lifecycle_status",
        "service_category",
        ["lifecycle_status"],
    )
    op.create_index("ix_service_category_parent_id", "service_category", ["parent_id"])

    # ── service_candidate ─────────────────────────────────────────────────────
    op.create_table(
        "service_candidate",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("href", sa.String(512), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(32), nullable=True),
        sa.Column(
            "lifecycle_status",
            sa.String(32),
            nullable=False,
            server_default="active",
        ),
        sa.Column("service_spec_id", sa.String(36), nullable=True),
        sa.Column("last_update", sa.String(64), nullable=True),
        sa.Column("type", sa.String(128), nullable=True),
        sa.Column("base_type", sa.String(128), nullable=True),
        sa.Column("schema_location", sa.String(512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["service_spec_id"],
            ["service_specification.id"],
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_service_candidate_name", "service_candidate", ["name"])
    op.create_index(
        "ix_service_candidate_lifecycle_status",
        "service_candidate",
        ["lifecycle_status"],
    )
    op.create_index(
        "ix_service_candidate_service_spec_id",
        "service_candidate",
        ["service_spec_id"],
    )

    # ── service_catalog ───────────────────────────────────────────────────────
    op.create_table(
        "service_catalog",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("href", sa.String(512), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(32), nullable=True),
        sa.Column(
            "lifecycle_status",
            sa.String(32),
            nullable=False,
            server_default="active",
        ),
        sa.Column("last_update", sa.String(64), nullable=True),
        sa.Column("type", sa.String(128), nullable=True),
        sa.Column("base_type", sa.String(128), nullable=True),
        sa.Column("schema_location", sa.String(512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_service_catalog_name", "service_catalog", ["name"])
    op.create_index(
        "ix_service_catalog_lifecycle_status",
        "service_catalog",
        ["lifecycle_status"],
    )

    # ── service_catalog_category (M2M) ────────────────────────────────────────
    op.create_table(
        "service_catalog_category",
        sa.Column("catalog_id", sa.String(36), nullable=False),
        sa.Column("category_id", sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(["catalog_id"], ["service_catalog.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["service_category.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("catalog_id", "category_id"),
    )

    # ── service_candidate_category (M2M) ─────────────────────────────────────
    op.create_table(
        "service_candidate_category",
        sa.Column("candidate_id", sa.String(36), nullable=False),
        sa.Column("category_id", sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"], ["service_candidate.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["category_id"], ["service_category.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("candidate_id", "category_id"),
    )


def downgrade() -> None:
    """Drop TMFC006 catalog extension tables in reverse order."""
    op.drop_table("service_candidate_category")
    op.drop_table("service_catalog_category")
    op.drop_table("service_catalog")
    op.drop_table("service_candidate")
    op.drop_table("service_category")
