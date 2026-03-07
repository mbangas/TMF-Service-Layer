"""characteristic_extensions

Revision ID: 0009_characteristic_extensions
Revises: 0008_catalog_tmfc006
Create Date: 2026-03-07 00:00:00.000000

Adds sub-entity tables for Characteristic management (TMF633 + TMF638):
  - characteristic_value_specification  (child of service_spec_characteristic)
  - characteristic_value                (child of service_characteristic)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009_characteristic_extensions"
down_revision: Union[str, None] = "0008_catalog_tmfc006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create characteristic sub-entity tables."""

    # ── characteristic_value_specification (TMF633) ───────────────────────────
    op.create_table(
        "characteristic_value_specification",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("value_type", sa.String(64), nullable=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("value_from", sa.String(128), nullable=True),
        sa.Column("value_to", sa.String(128), nullable=True),
        sa.Column("range_interval", sa.String(64), nullable=True),
        sa.Column("regex", sa.String(512), nullable=True),
        sa.Column("unit_of_measure", sa.String(64), nullable=True),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("char_spec_id", sa.String(36), nullable=False),
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
            ["char_spec_id"],
            ["service_spec_characteristic.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_characteristic_value_specification_char_spec_id",
        "characteristic_value_specification",
        ["char_spec_id"],
    )

    # ── characteristic_value (TMF638) ─────────────────────────────────────────
    op.create_table(
        "characteristic_value",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("value_type", sa.String(64), nullable=True),
        sa.Column("alias", sa.String(255), nullable=True),
        sa.Column("unit_of_measure", sa.String(64), nullable=True),
        sa.Column("char_id", sa.String(36), nullable=False),
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
            ["char_id"],
            ["service_characteristic.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_characteristic_value_char_id",
        "characteristic_value",
        ["char_id"],
    )


def downgrade() -> None:
    """Drop characteristic sub-entity tables."""
    op.drop_index("ix_characteristic_value_char_id", table_name="characteristic_value")
    op.drop_table("characteristic_value")

    op.drop_index(
        "ix_characteristic_value_specification_char_spec_id",
        table_name="characteristic_value_specification",
    )
    op.drop_table("characteristic_value_specification")
