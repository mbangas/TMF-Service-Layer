"""Service Test Management initial schema.

Creates tables: service_test_specification, service_test, test_measure.

Revision ID: 0007_testing_initial
Revises: 0006_assurance_initial
Create Date: 2026-03-07
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "0007_testing_initial"
down_revision = "0006_assurance_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── service_test_specification ────────────────────────────────────────────
    op.create_table(
        "service_test_specification",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("href", sa.String(512), nullable=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "state", sa.String(32), nullable=False, server_default="active", index=True
        ),
        sa.Column("test_type", sa.String(64), nullable=True),
        sa.Column("version", sa.String(16), nullable=True),
        sa.Column("valid_for_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_for_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("service_spec_id", sa.String(36), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["service_spec_id"],
            ["service_specification.id"],
            ondelete="RESTRICT",
        ),
    )

    # ── service_test ──────────────────────────────────────────────────────────
    op.create_table(
        "service_test",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("href", sa.String(512), nullable=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column(
            "state", sa.String(32), nullable=False, server_default="planned", index=True
        ),
        sa.Column("mode", sa.String(16), nullable=True),
        sa.Column("start_date_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("service_id", sa.String(36), nullable=False, index=True),
        sa.Column("test_spec_id", sa.String(36), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["service_id"], ["service.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["test_spec_id"],
            ["service_test_specification.id"],
            ondelete="RESTRICT",
        ),
    )

    # ── test_measure ──────────────────────────────────────────────────────────
    op.create_table(
        "test_measure",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("service_test_id", sa.String(36), nullable=False, index=True),
        sa.Column("metric_name", sa.String(255), nullable=False, index=True),
        sa.Column("metric_value", sa.Float, nullable=True),
        sa.Column("unit_of_measure", sa.String(64), nullable=True),
        sa.Column("result", sa.String(64), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["service_test_id"], ["service_test.id"], ondelete="CASCADE"
        ),
    )


def downgrade() -> None:
    op.drop_table("test_measure")
    op.drop_table("service_test")
    op.drop_table("service_test_specification")
