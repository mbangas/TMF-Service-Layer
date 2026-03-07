"""service_dependencies

Revision ID: 0010_service_dependencies
Revises: 0009_characteristic_extensions
Create Date: 2026-03-07 00:00:00.000000

Adds relationship tables for SID GB922 + TMF633 + TMF641 + TMF638:
  - service_spec_relationship        (ServiceSpecRelationship — TMF633 / SID GB922)
  - service_order_item_relationship  (ServiceOrderItemRelationship — TMF641)
  - service_relationship             (ServiceRelationship — TMF638 / SID GB922)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010_service_dependencies"
down_revision: Union[str, None] = "0009_characteristic_extensions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create service dependency / relationship tables."""

    # ── service_spec_relationship (TMF633 ServiceSpecRelationship) ────────────
    op.create_table(
        "service_spec_relationship",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("relationship_type", sa.String(64), nullable=False),
        sa.Column(
            "spec_id",
            sa.String(36),
            sa.ForeignKey("service_specification.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "related_spec_id",
            sa.String(36),
            sa.ForeignKey("service_specification.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("related_spec_name", sa.String(255), nullable=True),
        sa.Column("related_spec_href", sa.String(512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "spec_id", "related_spec_id", "relationship_type",
            name="uq_spec_relationship",
        ),
    )

    # ── service_order_item_relationship (TMF641 ServiceOrderItemRelationship) ──
    op.create_table(
        "service_order_item_relationship",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("relationship_type", sa.String(64), nullable=False),
        sa.Column(
            "order_item_orm_id",
            sa.String(36),
            sa.ForeignKey("service_order_item.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # TMF641: items reference each other by the client-assigned label (e.g. "1", "2")
        sa.Column("related_item_label", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # ── service_relationship (TMF638 ServiceRelationship / SID GB922) ─────────
    op.create_table(
        "service_relationship",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("relationship_type", sa.String(64), nullable=False),
        sa.Column(
            "service_id",
            sa.String(36),
            sa.ForeignKey("service.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "related_service_id",
            sa.String(36),
            sa.ForeignKey("service.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("related_service_name", sa.String(255), nullable=True),
        sa.Column("related_service_href", sa.String(512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "service_id", "related_service_id", "relationship_type",
            name="uq_service_relationship",
        ),
    )


def downgrade() -> None:
    """Drop service dependency / relationship tables."""
    op.drop_table("service_relationship")
    op.drop_table("service_order_item_relationship")
    op.drop_table("service_spec_relationship")
