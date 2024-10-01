"""Add model version

Revision ID: 1.0.7
Revises:
Create Date: 2024-10-01 14:00

"""

from alembic import op
from sqlalchemy import BigInteger, Column, String

revision = "1.0.7"
down_revision = "1.0.6"
branch_labels = "add_version"
depends_on = "1.0.6"

def upgrade():
    op.add_column('jobs', Column("process_version", String()))

def downgrade():
    op.drop_column('jobs', 'process_version')
