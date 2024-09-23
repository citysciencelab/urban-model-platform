"""Extend ensembles

Revision ID: 1.0.3
Revises:
Create Date: 2024-09-23 14:00

"""

from alembic import op
from sqlalchemy import BigInteger, Column, String

revision = "1.0.3"
down_revision = "1.0.2"
branch_labels = "extend_ensembles"
depends_on = "1.0.2"


def upgrade():
    op.add_column("ensembles", Column("sample_size", BigInteger()))
    op.add_column("ensembles", Column("sampling_method", String()))


def downgrade():
    op.drop_column("ensembles", "sample_size")
    op.drop_column("ensembles", "sampling_method")
