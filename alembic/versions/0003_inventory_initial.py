"""TMF638 Service Inventory — initial schema.

Revision ID: 0003_inventory_initial
Revises: 0002_order_initial
Create Date: 2026-03-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_inventory_initial"
down_revision: str | None = "0002_order_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the ``service`` and ``service_characteristic`` tables."""

    # ── service ───────────────────────────────────────────────────────────────
    op.create_table(
        "service",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("href", sa.String(512), nullable=True),

        # Core entity fields
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("service_type", sa.String(128), nullable=True),

        # Lifecycle
        sa.Column("state", sa.String(32), nullable=False, server_default="inactive"),

        # Dates
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),

        # TMF annotation fields
        sa.Column("type", sa.String(128), nullable=True),
        sa.Column("base_type", sa.String(128), nullable=True),
        sa.Column("schema_location", sa.String(512), nullable=True),

        # Cross-domain FK references
        sa.Column("service_spec_id", sa.String(36), nullable=True),
        sa.Column("service_order_id", sa.String(36), nullable=True),

        # Timestamps (managed by the application / DB trigger)
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
            onupdate=sa.func.now(),
            nullable=False,
        ),

        # FK to service_specification — RESTRICT so a spec cannot be deleted while
        # a Service instance references it
        sa.ForeignKeyConstraint(
            ["service_spec_id"],
            ["service_specification.id"],
            ondelete="RESTRICT",
            name="fk_service_service_spec_id",
        ),

        # FK to service_order — SET NULL so deleting an order does not orphan
        # existing inventory records
        sa.ForeignKeyConstraint(
            ["service_order_id"],
            ["service_order.id"],
            ondelete="SET NULL",
            name="fk_service_service_order_id",
        ),
    )

    op.create_index("ix_service_name", "service", ["name"])
    op.create_index("ix_service_state", "service", ["state"])
    op.create_index("ix_service_service_spec_id", "service", ["service_spec_id"])
    op.create_index("ix_service_service_order_id", "service", ["service_order_id"])

    # ── service_characteristic ─────────────────────────────────────────────────
    op.create_table(
        "service_characteristic",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("value_type", sa.String(64), nullable=True),

        # FK → parent service (CASCADE — removing a service removes its characteristics)
        sa.Column("service_id", sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["service.id"],
            ondelete="CASCADE",
            name="fk_service_characteristic_service_id",
        ),

        # Timestamps
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
            onupdate=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_index("ix_service_characteristic_service_id", "service_characteristic", ["service_id"])


def downgrade() -> None:
    """Drop the ``service_characteristic`` and ``service`` tables."""
    op.drop_index("ix_service_characteristic_service_id", table_name="service_characteristic")
    op.drop_table("service_characteristic")

    op.drop_index("ix_service_service_order_id", table_name="service")
    op.drop_index("ix_service_service_spec_id", table_name="service")
    op.drop_index("ix_service_state", table_name="service")
    op.drop_index("ix_service_name", table_name="service")
    op.drop_table("service")
