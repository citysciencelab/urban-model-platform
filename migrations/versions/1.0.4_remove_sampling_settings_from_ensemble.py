"""Remove sampling settings from ensemble

Revision ID: 1.0.4
Revises:
Create Date: 2024-09-23 14:00

"""

from alembic import op
from sqlalchemy import BigInteger, Column, String

revision = "1.0.4"
down_revision = "1.0.3"
branch_labels = "remove_sampling_settings_from_ensemble"
depends_on = "1.0.3"


def upgrade():
    op.drop_column("ensembles", "sample_size")
    op.drop_column("ensembles", "sampling_method")


def downgrade():
    op.add_column("ensembles", Column("sample_size", BigInteger()))
    op.add_column("ensembles", Column("sampling_method", String()))
