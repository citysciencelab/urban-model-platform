"""Add user

Revision ID: 1.0.0
Revises:
Create Date: 2024-08-20 08:13:59.521824

"""
from alembic import op
from sqlalchemy import Column, String

# revision identifiers, used by Alembic.
revision = '1.0.0'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('jobs', Column('user_id', String()))

def downgrade():
    pass
