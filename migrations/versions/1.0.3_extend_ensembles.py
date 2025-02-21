"""Extend ensembles

Revision ID: 1.0.3
Revises:
Create Date: 2024-09-23 14:00

"""

from alembic import op
from sqlalchemy import BigInteger, Column, DateTime, String

revision = "1.0.3"
down_revision = "1.0.2"
branch_labels = "extend_ensembles"
depends_on = "1.0.2"


def upgrade():
    op.add_column("ensembles", Column("sample_size", BigInteger()))
    op.add_column("ensembles", Column("sampling_method", String()))
    op.add_column("ensembles", Column("created", DateTime()))
    op.add_column("ensembles", Column("modified", DateTime()))

    op.add_column("ensemble_comments", Column("created", DateTime()))
    op.add_column("ensemble_comments", Column("modified", DateTime()))


def downgrade():
    op.drop_column("ensembles", "sample_size")
    op.drop_column("ensembles", "sampling_method")
    op.drop_column("ensembles", "created")
    op.drop_column("ensembles", "modified")

    op.drop_column("ensemble_comments", "created")
    op.drop_column("ensemble_comments", "modified")
