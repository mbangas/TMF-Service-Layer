"""TMF640 Service Activation & Configuration — initial schema.

Revision ID: 0004_provisioning_initial
Revises: 0003_inventory_initial
Create Date: 2026-03-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_provisioning_initial"
down_revision: str | None = "0003_inventory_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the ``service_activation_job`` and ``service_configuration_param`` tables."""

    # ── service_activation_job ────────────────────────────────────────────────
    op.create_table(
        "service_activation_job",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("href", sa.String(512), nullable=True),

        # Core entity fields
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),

        # Job type: provision | activate | modify | deactivate | terminate
        sa.Column("job_type", sa.String(32), nullable=False),

        # Lifecycle state (default: accepted)
        sa.Column("state", sa.String(32), nullable=False, server_default="accepted"),

        # Execution mode
        sa.Column("mode", sa.String(32), nullable=True),
        sa.Column("start_mode", sa.String(32), nullable=True),

        # Scheduling / actuals
        sa.Column("scheduled_start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_completion_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_completion_date", sa.DateTime(timezone=True), nullable=True),

        # Failure info
        sa.Column("error_message", sa.Text(), nullable=True),

        # TMF annotation fields
        sa.Column("type", sa.String(128), nullable=True),
        sa.Column("base_type", sa.String(128), nullable=True),
        sa.Column("schema_location", sa.String(512), nullable=True),

        # FK → service (RESTRICT — a Service with pending/running jobs cannot be deleted)
        sa.Column("service_id", sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["service.id"],
            ondelete="RESTRICT",
            name="fk_service_activation_job_service_id",
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

    op.create_index("ix_service_activation_job_name", "service_activation_job", ["name"])
    op.create_index("ix_service_activation_job_state", "service_activation_job", ["state"])
    op.create_index("ix_service_activation_job_job_type", "service_activation_job", ["job_type"])
    op.create_index("ix_service_activation_job_service_id", "service_activation_job", ["service_id"])

    # ── service_configuration_param ───────────────────────────────────────────
    op.create_table(
        "service_configuration_param",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("value_type", sa.String(64), nullable=True),

        # FK → parent job (CASCADE — deleting a job removes its params)
        sa.Column("job_id", sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["service_activation_job.id"],
            ondelete="CASCADE",
            name="fk_service_configuration_param_job_id",
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

    op.create_index(
        "ix_service_configuration_param_job_id",
        "service_configuration_param",
        ["job_id"],
    )


def downgrade() -> None:
    """Drop the ``service_configuration_param`` and ``service_activation_job`` tables."""
    op.drop_index(
        "ix_service_configuration_param_job_id",
        table_name="service_configuration_param",
    )
    op.drop_table("service_configuration_param")

    op.drop_index("ix_service_activation_job_service_id", table_name="service_activation_job")
    op.drop_index("ix_service_activation_job_job_type", table_name="service_activation_job")
    op.drop_index("ix_service_activation_job_state", table_name="service_activation_job")
    op.drop_index("ix_service_activation_job_name", table_name="service_activation_job")
    op.drop_table("service_activation_job")
