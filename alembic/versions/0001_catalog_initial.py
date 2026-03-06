"""catalog_initial

Revision ID: 0001_catalog_initial
Revises:
Create Date: 2026-03-06 00:00:00.000000

Creates tables for TMF633 Service Catalog Management:
  - service_specification
  - service_spec_characteristic
  - service_level_specification
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_catalog_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create catalog tables."""
    # ── service_specification ─────────────────────────────────────────────────
    op.create_table(
        "service_specification",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("href", sa.String(512), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(32), nullable=True),
        sa.Column("lifecycle_status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("is_bundle", sa.Boolean(), nullable=False, server_default=sa.false()),
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
    op.create_index("ix_service_specification_name", "service_specification", ["name"])
    op.create_index(
        "ix_service_specification_lifecycle_status",
        "service_specification",
        ["lifecycle_status"],
    )

    # ── service_spec_characteristic ───────────────────────────────────────────
    op.create_table(
        "service_spec_characteristic",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("value_type", sa.String(64), nullable=True),
        sa.Column("is_unique", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("min_cardinality", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_cardinality", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("extensible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("service_spec_id", sa.String(36), nullable=False),
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
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_service_spec_characteristic_service_spec_id",
        "service_spec_characteristic",
        ["service_spec_id"],
    )

    # ── service_level_specification ───────────────────────────────────────────
    op.create_table(
        "service_level_specification",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("validity_period_start", sa.String(64), nullable=True),
        sa.Column("validity_period_end", sa.String(64), nullable=True),
        sa.Column("service_spec_id", sa.String(36), nullable=False),
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
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_service_level_specification_service_spec_id",
        "service_level_specification",
        ["service_spec_id"],
    )


def downgrade() -> None:
    """Drop catalog tables in reverse order."""
    op.drop_table("service_level_specification")
    op.drop_table("service_spec_characteristic")
    op.drop_table("service_specification")
