"""Assurance module initial schema — alarm, performance_measurement, service_level_objective.

Revision ID: 0006_assurance_initial
Revises: 0005_qualification_initial
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0006_assurance_initial"
down_revision = "0005_qualification_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── alarm ──────────────────────────────────────────────────────────────────
    op.create_table(
        "alarm",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("href", sa.String(512), nullable=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("state", sa.String(32), nullable=False, server_default="raised", index=True),
        sa.Column("alarm_type", sa.String(64), nullable=True),
        sa.Column("severity", sa.String(32), nullable=True),
        sa.Column("probable_cause", sa.String(255), nullable=True),
        sa.Column("specific_problem", sa.Text, nullable=True),
        sa.Column("service_id", sa.String(36), nullable=False, index=True),
        sa.Column("raised_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["service_id"], ["service.id"], ondelete="RESTRICT"),
    )

    # ── performance_measurement ────────────────────────────────────────────────
    op.create_table(
        "performance_measurement",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("href", sa.String(512), nullable=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("state", sa.String(32), nullable=False, server_default="scheduled", index=True),
        sa.Column("metric_name", sa.String(255), nullable=False, index=True),
        sa.Column("metric_value", sa.Float, nullable=True),
        sa.Column("unit_of_measure", sa.String(64), nullable=True),
        sa.Column("granularity", sa.String(64), nullable=True),
        sa.Column("service_id", sa.String(36), nullable=False, index=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["service_id"], ["service.id"], ondelete="RESTRICT"),
    )

    # ── service_level_objective ────────────────────────────────────────────────
    op.create_table(
        "service_level_objective",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("href", sa.String(512), nullable=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("state", sa.String(32), nullable=False, server_default="active", index=True),
        sa.Column("metric_name", sa.String(255), nullable=False, index=True),
        sa.Column("threshold_value", sa.Float, nullable=True),
        sa.Column("direction", sa.String(16), nullable=True),
        sa.Column("tolerance", sa.Float, nullable=True),
        sa.Column("service_id", sa.String(36), nullable=False, index=True),
        sa.Column("sls_id", sa.String(36), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["service_id"], ["service.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["sls_id"], ["service_level_specification.id"], ondelete="RESTRICT"
        ),
    )


def downgrade() -> None:
    op.drop_table("service_level_objective")
    op.drop_table("performance_measurement")
    op.drop_table("alarm")
