"""Refactor jobs

Revision ID: 1.0.5
Revises:
Create Date: 2024-09-17 11:14

"""
from alembic import op
from sqlalchemy import Column, String, BigInteger, DateTime
from sqlalchemy.dialects.postgresql import JSONB

revision = '1.0.5'
down_revision = '1.0.4'
branch_labels = 'refactor_jobs'
depends_on = '1.0.4'

def upgrade():
    op.create_table(
        'job_configs',
        Column('id', BigInteger(), primary_key = True),
        Column('process_id', String()),
        Column('provider_prefix', String()),
        Column('provider_url', String()),
        Column('message', String()),
        Column('parameters', JSONB()),
        Column('user_id', String(), index = True),
        Column('process_title', String()),
        Column('name', String()),
    )
    op.create_table(
        'job_configs_ensembles',
        Column('ensemble_id', BigInteger(), index = True),
        Column('job_config_id', BigInteger(), index = True)
    )
    op.create_table(
        'job_executions',
        Column('id', BigInteger(), primary_key = True),
        Column('job_config_id', BigInteger(), index = True),
        Column('job_id', String()),
        Column('remote_job_id', String()),
        Column('status', String()),
        Column('message', String()),
        Column('created', DateTime()),
        Column('started', DateTime()),
        Column('finished', DateTime()),
        Column('updated', DateTime()),
        Column('progress', BigInteger()),
        Column('results_metadata', JSONB()),
        Column('user_id', String(), index = True)
    )

def downgrade():
    op.drop_table('job_configs')
    op.drop_table('job_configs_ensembles')
    op.drop_table('job_executions')
