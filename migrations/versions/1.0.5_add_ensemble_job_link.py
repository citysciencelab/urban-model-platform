"""Add link between jobs and ensembles

Revision ID: 1.0.5
Revises:
Create Date: 2024-09-27 14:00

"""

from alembic import op
from sqlalchemy import BigInteger, Column, String

revision = "1.0.5"
down_revision = "1.0.4"
branch_labels = "add_link_between_jobs_and_ensembles"
depends_on = "1.0.4"

def upgrade():
    op.create_table(
        'jobs_ensembles',
        Column('id', BigInteger(), primary_key = True),
        Column('ensemble_id', BigInteger(), index = True),
        Column('job_id', String(), index = True)
    )

def downgrade():
    op.drop_table(
        'jobs_ensembles'
    )
