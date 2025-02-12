"""create_jobs_table_initial

Revision ID: e4478f461de1
Revises: 1.0.11
Create Date: 2025-02-07 08:39:56.443236

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4478f461de1'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade():
    op.create_table(
        'jobs',
        sa.Column('process_id', sa.String(80)),
        sa.Column('job_id', sa.String(80), primary_key=True),
        sa.Column('remote_job_id', sa.String(80)),
        sa.Column('provider_prefix', sa.String(80)),
        sa.Column('provider_url', sa.String(80)),
        sa.Column('status', sa.Enum('accepted', 'running', 'successful', 'failed', 'dismissed', name='status')),
        sa.Column('message', sa.String),
        sa.Column('created', sa.DateTime),
        sa.Column('started', sa.DateTime),
        sa.Column('finished', sa.DateTime),
        sa.Column('updated', sa.DateTime),
        sa.Column('progress', sa.Integer),
        sa.Column('parameters', sa.JSON),
        sa.Column('results_metadata', sa.JSON)
    )

def downgrade():
    op.drop_table('jobs')