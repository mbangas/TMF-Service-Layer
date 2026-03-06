"""order_initial

Revision ID: 0002_order_initial
Revises: 0001_catalog_initial
Create Date: 2026-03-06 00:00:00.000000

Creates tables for TMF641 Service Order Management:
  - service_order
  - service_order_item
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_order_initial"
down_revision: Union[str, None] = "0001_catalog_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create service order tables."""
    # ── service_order ─────────────────────────────────────────────────────────
    op.create_table(
        "service_order",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("href", sa.String(512), nullable=True),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("priority", sa.String(32), nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(255), nullable=True),
        sa.Column("state", sa.String(32), nullable=False, server_default="acknowledged"),
        sa.Column("order_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completion_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_completion_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expected_completion_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
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
    op.create_index("ix_service_order_state", "service_order", ["state"])

    # ── service_order_item ────────────────────────────────────────────────────
    op.create_table(
        "service_order_item",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("order_item_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(32), nullable=False, server_default="add"),
        sa.Column("state", sa.String(32), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("service_order_id", sa.String(36), nullable=False),
        sa.Column("service_spec_id", sa.String(36), nullable=True),
        sa.Column("service_spec_href", sa.String(512), nullable=True),
        sa.Column("service_spec_name", sa.String(255), nullable=True),
        sa.Column("service_name", sa.String(255), nullable=True),
        sa.Column("service_description", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
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
            ["service_order_id"],
            ["service_order.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["service_spec_id"],
            ["service_specification.id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_service_order_item_service_order_id",
        "service_order_item",
        ["service_order_id"],
    )
    op.create_index(
        "ix_service_order_item_service_spec_id",
        "service_order_item",
        ["service_spec_id"],
    )


def downgrade() -> None:
    """Drop service order tables in reverse order."""
    op.drop_table("service_order_item")
    op.drop_table("service_order")
