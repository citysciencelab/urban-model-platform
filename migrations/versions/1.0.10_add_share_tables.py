"""Add share tables

Revision ID: 1.0.10
Revises:
Create Date: 2024-10-02 14:00

"""

from alembic import op
from sqlalchemy import BigInteger, Column, String

revision = "1.0.10"
down_revision = "1.0.9"
branch_labels = "add_share_tables"
depends_on = "1.0.9"

def upgrade():
    op.create_table(
        'jobs_users',
        Column('id', BigInteger(), primary_key = True),
        Column('job_id', String(), index = True),
        Column('user_id', String(), index = True),
    )
    op.create_table(
        'ensembles_users',
        Column('id', BigInteger(), primary_key = True),
        Column('ensemble_id', BigInteger(), index = True),
        Column('user_id', String(), index = True),
    )

def downgrade():
    op.drop_table('jobs_users')
    op.drop_table('ensembles_users')
