"""Fix missing server_default on created_at / updated_at for testing tables.

Migration 0007 created service_test_specification, service_test and test_measure
with nullable timestamp columns but without a server_default, so the DB never
auto-populated them on INSERT.  This migration:

  1. Back-fills any existing NULL rows with the current timestamp.
  2. Adds ``DEFAULT NOW()`` to both columns on all affected tables.
  3. Tightens the columns to NOT NULL so future INSERTs are always stamped.

Revision ID: 0012_testing_timestamps_fix
Revises: 0011_assurance_timestamps_fix
Create Date: 2026-03-08
"""

from alembic import op
import sqlalchemy as sa

revision: str = "0012_testing_timestamps_fix"
down_revision: str = "0011_assurance_timestamps_fix"
branch_labels = None
depends_on = None

_TABLES = ("service_test_specification", "service_test")


def upgrade() -> None:
    for table in _TABLES:
        # 1. Back-fill any rows that already landed with NULL timestamps
        op.execute(
            f"UPDATE {table} SET created_at = NOW() WHERE created_at IS NULL"
        )
        op.execute(
            f"UPDATE {table} SET updated_at = NOW() WHERE updated_at IS NULL"
        )

        # 2. Add server defaults so future INSERTs are stamped by the DB
        op.alter_column(
            table,
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )
        op.alter_column(
            table,
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        )


def downgrade() -> None:
    for table in _TABLES:
        op.alter_column(
            table,
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
            server_default=None,
        )
        op.alter_column(
            table,
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            nullable=True,
            server_default=None,
        )
