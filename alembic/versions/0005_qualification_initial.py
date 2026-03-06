"""TMF645 Service Qualification Management — initial schema.

Revision ID: 0005_qualification_initial
Revises: 0004_provisioning_initial
Create Date: 2026-03-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_qualification_initial"
down_revision: str | None = "0004_provisioning_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the ``service_qualification`` and ``service_qualification_item`` tables."""

    # ── service_qualification ─────────────────────────────────────────────────
    op.create_table(
        "service_qualification",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("href", sa.String(512), nullable=True),

        # Core entity fields
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),

        # Lifecycle state (default: acknowledged)
        sa.Column("state", sa.String(32), nullable=False, server_default="acknowledged"),

        # Scheduling / expiry
        sa.Column("expected_qualification_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expiration_date", sa.DateTime(timezone=True), nullable=True),

        # TMF annotation fields
        sa.Column("type", sa.String(128), nullable=True),
        sa.Column("base_type", sa.String(128), nullable=True),
        sa.Column("schema_location", sa.String(512), nullable=True),

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

    op.create_index("ix_service_qualification_name", "service_qualification", ["name"])
    op.create_index("ix_service_qualification_state", "service_qualification", ["state"])

    # ── service_qualification_item ────────────────────────────────────────────
    op.create_table(
        "service_qualification_item",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),

        # FK → parent qualification (CASCADE — deleting a qualification removes items)
        sa.Column("qualification_id", sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(
            ["qualification_id"],
            ["service_qualification.id"],
            ondelete="CASCADE",
            name="fk_service_qualification_item_qualification_id",
        ),

        # Optional FK → service specification (SET NULL on delete)
        sa.Column("service_spec_id", sa.String(36), nullable=True),
        sa.ForeignKeyConstraint(
            ["service_spec_id"],
            ["service_specification.id"],
            ondelete="SET NULL",
            name="fk_service_qualification_item_service_spec_id",
        ),

        # Item result state (default: approved)
        sa.Column("state", sa.String(32), nullable=False, server_default="approved"),

        # Qualification result details
        sa.Column("qualifier_message", sa.Text(), nullable=True),
        sa.Column("termination_error", sa.Text(), nullable=True),

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

    op.create_index(
        "ix_service_qualification_item_qualification_id",
        "service_qualification_item",
        ["qualification_id"],
    )
    op.create_index(
        "ix_service_qualification_item_service_spec_id",
        "service_qualification_item",
        ["service_spec_id"],
    )
    op.create_index(
        "ix_service_qualification_item_state",
        "service_qualification_item",
        ["state"],
    )


def downgrade() -> None:
    """Drop the ``service_qualification_item`` and ``service_qualification`` tables."""
    op.drop_index("ix_service_qualification_item_state", table_name="service_qualification_item")
    op.drop_index(
        "ix_service_qualification_item_service_spec_id",
        table_name="service_qualification_item",
    )
    op.drop_index(
        "ix_service_qualification_item_qualification_id",
        table_name="service_qualification_item",
    )
    op.drop_table("service_qualification_item")

    op.drop_index("ix_service_qualification_state", table_name="service_qualification")
    op.drop_index("ix_service_qualification_name", table_name="service_qualification")
    op.drop_table("service_qualification")
