"""Add agent runtime settings.

Revision ID: 0002_agent_runtime_settings
Revises: 0001_initial_schema
Create Date: 2026-06-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_agent_runtime_settings"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "agent_runtime_settings",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("llm_provider", sa.String(length=40), nullable=False),
        sa.Column("llm_base_url", sa.Text(), nullable=True),
        sa.Column("llm_model", sa.String(length=255), nullable=True),
        sa.Column("encrypted_llm_api_key", sa.Text(), nullable=True),
        sa.Column("pi_enabled", sa.Boolean(), nullable=False),
        sa.Column("pi_command", sa.Text(), nullable=False),
        sa.Column("pi_work_dir", sa.Text(), nullable=False),
        sa.Column("pi_max_rounds", sa.Integer(), nullable=False),
        sa.Column("pi_timeout_minutes", sa.Integer(), nullable=False),
        *timestamps(),
    )


def downgrade() -> None:
    op.drop_table("agent_runtime_settings")
