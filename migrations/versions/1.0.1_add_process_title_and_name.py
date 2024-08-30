"""Add process title

Revision ID: 1.0.1
Revises:
Create Date: 2024-08-29 11:14

"""
from alembic import op
from sqlalchemy import Column, String

# revision identifiers, used by Alembic.
revision = '1.0.1'
down_revision = '1.0.0'
branch_labels = 'add_process_title_and_name'
depends_on = '1.0.0'


def upgrade():
    op.add_column('jobs', Column('process_title', String()))
    op.add_column('jobs', Column('name', String()))

def downgrade():
    pass
