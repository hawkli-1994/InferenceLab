"""Initial MVP schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "machines",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=120), nullable=False),
        sa.Column("credential_type", sa.String(length=40), nullable=False),
        sa.Column("encrypted_credential", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("runtime_mode", sa.String(length=40), nullable=False),
        sa.Column("machine_profile", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=True),
        *timestamps(),
    )
    op.create_index("ix_machines_fingerprint", "machines", ["fingerprint"])

    op.create_table(
        "machine_snapshots",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("machine_id", sa.String(length=36), sa.ForeignKey("machines.id"), nullable=False),
        sa.Column("profile", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("artifact_uri", sa.Text(), nullable=True),
        *timestamps(),
    )
    op.create_index("ix_machine_snapshots_fingerprint", "machine_snapshots", ["fingerprint"])

    op.create_table(
        "bootstrap_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("machine_id", sa.String(length=36), sa.ForeignKey("machines.id"), nullable=False),
        sa.Column("profile", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("modules", sa.JSON(), nullable=False),
        sa.Column("step_results", sa.JSON(), nullable=False),
        sa.Column("failure_class", sa.String(length=80), nullable=True),
        sa.Column("failure_hint", sa.Text(), nullable=True),
        *timestamps(),
    )

    op.create_table(
        "models",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("format", sa.String(length=80), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("cache_path", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *timestamps(),
    )

    op.create_table(
        "images",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("tag", sa.String(length=120), nullable=False),
        sa.Column("digest", sa.String(length=140), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *timestamps(),
    )

    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("kind", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("uri", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        *timestamps(),
    )

    op.create_table(
        "experiments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("machine_id", sa.String(length=36), sa.ForeignKey("machines.id"), nullable=False),
        sa.Column("model_id", sa.String(length=36), sa.ForeignKey("models.id"), nullable=False),
        sa.Column("runtime_mode", sa.String(length=40), nullable=False),
        sa.Column("framework", sa.String(length=80), nullable=False),
        sa.Column("framework_version", sa.String(length=80), nullable=False),
        sa.Column("framework_params", sa.JSON(), nullable=False),
        sa.Column("prompt_dataset", sa.String(length=180), nullable=False),
        sa.Column("launch_command", sa.Text(), nullable=False),
        sa.Column("goal", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("reproducibility", sa.JSON(), nullable=False),
        *timestamps(),
    )

    op.create_table(
        "experiment_trials",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "experiment_id", sa.String(length=36), sa.ForeignKey("experiments.id"), nullable=False
        ),
        sa.Column("trial_index", sa.Integer(), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("launch_command", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("failure_category", sa.String(length=80), nullable=True),
        *timestamps(),
    )

    op.create_table(
        "metrics_summary",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "experiment_id", sa.String(length=36), sa.ForeignKey("experiments.id"), nullable=False
        ),
        sa.Column(
            "trial_id", sa.String(length=36), sa.ForeignKey("experiment_trials.id"), nullable=True
        ),
        sa.Column("ttft_p50_ms", sa.Float(), nullable=False),
        sa.Column("tpot_p50_ms", sa.Float(), nullable=False),
        sa.Column("latency_p99_ms", sa.Float(), nullable=False),
        sa.Column("tokens_per_second", sa.Float(), nullable=False),
        sa.Column("requests_per_second", sa.Float(), nullable=False),
        sa.Column("failure_rate", sa.Float(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        *timestamps(),
    )

    op.create_table(
        "metrics_samples",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "experiment_id", sa.String(length=36), sa.ForeignKey("experiments.id"), nullable=False
        ),
        sa.Column(
            "trial_id", sa.String(length=36), sa.ForeignKey("experiment_trials.id"), nullable=True
        ),
        sa.Column("sampled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("job_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("logs", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        *timestamps(),
    )

    op.create_table(
        "reports",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "experiment_id", sa.String(length=36), sa.ForeignKey("experiments.id"), nullable=False
        ),
        sa.Column("template", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column(
            "artifact_id", sa.String(length=36), sa.ForeignKey("artifacts.id"), nullable=True
        ),
        *timestamps(),
    )


def downgrade() -> None:
    for table in (
        "reports",
        "jobs",
        "metrics_samples",
        "metrics_summary",
        "experiment_trials",
        "experiments",
        "artifacts",
        "images",
        "models",
        "bootstrap_runs",
        "machine_snapshots",
        "machines",
    ):
        op.drop_table(table)
