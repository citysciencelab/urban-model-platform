"""Add postgis extension

Revision ID: 1.0.6
Revises:
Create Date: 2024-10-01 14:00

"""

from alembic import op
from sqlalchemy import BigInteger, Column, String

revision = "1.0.6"
down_revision = "1.0.5"
branch_labels = "add_postgis_extension"
depends_on = "1.0.5"

def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS postgis')

def downgrade():
    op.execute('drop extension postgis')