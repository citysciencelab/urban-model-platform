"""Add ensembles

Revision ID: 1.0.2
Revises:
Create Date: 2024-09-17 11:14

"""
from alembic import op
from sqlalchemy import Column, String, BigInteger
from sqlalchemy.dialects.postgresql import JSONB

revision = '1.0.2'
down_revision = '1.0.1'
branch_labels = 'add_ensembles'
depends_on = '1.0.1'


def upgrade():
    op.create_table(
        'ensembles',
        Column('id', BigInteger(), primary_key = True),
        Column('name', String()),
        Column('description', String()),
        Column('user_id', String(), index = True),
        Column('scenario_configs', JSONB())
    )
    op.create_table(
        'ensemble_comments',
        Column('id', BigInteger(), primary_key = True),
        Column('user_id', String(), index = True),
        Column('ensemble_id', BigInteger(), index = True),
        Column('comment', String())
    )
    op.add_column('jobs', Column('ensemble_id', BigInteger(), index = True))

def downgrade():
    op.drop_table('ensemble_comments')
    op.drop_table('ensembles')
    op.drop_column('jobs', 'ensemble_id')
