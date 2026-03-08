"""Problem management initial schema — trouble_ticket, trouble_ticket_note, service_problem.

Revision ID: 0013_problem_initial
Revises: 0012_testing_timestamps_fix
Create Date: 2026-03-08
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0013_problem_initial"
down_revision = "0012_testing_timestamps_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── trouble_ticket ─────────────────────────────────────────────────────────
    op.create_table(
        "trouble_ticket",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("href", sa.String(512), nullable=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("state", sa.String(32), nullable=False, server_default="submitted", index=True),
        sa.Column("severity", sa.String(32), nullable=True, index=True),
        sa.Column("priority", sa.Integer, nullable=True),
        sa.Column("ticket_type", sa.String(64), nullable=True),
        sa.Column("resolution", sa.Text, nullable=True),
        sa.Column("expected_resolution_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("related_service_id", sa.String(36), nullable=True, index=True),
        sa.Column("related_alarm_id", sa.String(36), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["related_service_id"], ["service.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["related_alarm_id"], ["alarm.id"], ondelete="SET NULL"),
    )

    # ── trouble_ticket_note ────────────────────────────────────────────────────
    op.create_table(
        "trouble_ticket_note",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("note_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ticket_id", sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(["ticket_id"], ["trouble_ticket.id"], ondelete="CASCADE"),
    )

    # ── service_problem ────────────────────────────────────────────────────────
    op.create_table(
        "service_problem",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("href", sa.String(512), nullable=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("state", sa.String(32), nullable=False, server_default="submitted", index=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("impact", sa.String(64), nullable=True, index=True),
        sa.Column("priority", sa.Integer, nullable=True),
        sa.Column("root_cause", sa.Text, nullable=True),
        sa.Column("resolution", sa.Text, nullable=True),
        sa.Column("expected_resolution_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("related_service_id", sa.String(36), nullable=True, index=True),
        sa.Column("related_ticket_id", sa.String(36), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["related_service_id"], ["service.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["related_ticket_id"], ["trouble_ticket.id"], ondelete="SET NULL"),
    )


def downgrade() -> None:
    op.drop_table("service_problem")
    op.drop_table("trouble_ticket_note")
    op.drop_table("trouble_ticket")
