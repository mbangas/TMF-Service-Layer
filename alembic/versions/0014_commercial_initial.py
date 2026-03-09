"""Commercial module initial schema — quote, quote_item, agreement, service_level_agreement.

Revision ID: 0014_commercial_initial
Revises: 0013_problem_initial
Create Date: 2026-03-09
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0014_commercial_initial"
down_revision = "0013_problem_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── quote ──────────────────────────────────────────────────────────────────
    op.create_table(
        "quote",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("href", sa.String(512), nullable=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("state", sa.String(32), nullable=False, server_default="inProgress", index=True),
        sa.Column("quote_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("requested_completion_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expected_fulfillment_start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completion_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("related_service_spec_id", sa.String(36), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["related_service_spec_id"], ["service_specification.id"], ondelete="RESTRICT"),
    )

    # ── quote_item ─────────────────────────────────────────────────────────────
    op.create_table(
        "quote_item",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("action", sa.String(32), nullable=False, server_default="add"),
        sa.Column("state", sa.String(32), nullable=False, server_default="inProgress"),
        sa.Column("quantity", sa.Integer, nullable=True, server_default="1"),
        sa.Column("item_price", sa.Numeric(15, 2), nullable=True),
        sa.Column("price_type", sa.String(32), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("quote_id", sa.String(36), nullable=False, index=True),
        sa.Column("related_service_spec_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["quote_id"], ["quote.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["related_service_spec_id"], ["service_specification.id"], ondelete="RESTRICT"),
    )

    # ── agreement ─────────────────────────────────────────────────────────────
    op.create_table(
        "agreement",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("href", sa.String(512), nullable=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("agreement_type", sa.String(64), nullable=True),
        sa.Column("state", sa.String(32), nullable=False, server_default="inProgress", index=True),
        sa.Column("document_number", sa.String(64), nullable=True),
        sa.Column("version", sa.String(32), nullable=True, server_default="1.0"),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status_change_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("related_service_spec_id", sa.String(36), nullable=True, index=True),
        sa.Column("related_quote_id", sa.String(36), nullable=True, index=True),
        sa.Column("related_service_id", sa.String(36), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["related_service_spec_id"], ["service_specification.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["related_quote_id"], ["quote.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["related_service_id"], ["service.id"], ondelete="RESTRICT"),
    )

    # ── service_level_agreement ────────────────────────────────────────────────
    op.create_table(
        "service_level_agreement",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("metric", sa.String(64), nullable=False),
        sa.Column("metric_threshold", sa.Numeric(15, 4), nullable=False),
        sa.Column("metric_unit", sa.String(32), nullable=True),
        sa.Column("conformance_period", sa.String(32), nullable=True),
        sa.Column("agreement_id", sa.String(36), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["agreement_id"], ["agreement.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("service_level_agreement")
    op.drop_table("agreement")
    op.drop_table("quote_item")
    op.drop_table("quote")
