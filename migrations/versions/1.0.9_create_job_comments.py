"""Create job comments

Revision ID: 1.0.9
Revises:
Create Date: 2024-10-01 14:00

"""

from alembic import op
from sqlalchemy import BigInteger, Column, DateTime, String

revision = "1.0.9"
down_revision = "1.0.8"
branch_labels = "create_job_comments"
depends_on = "1.0.8"

def upgrade():
    op.create_table(
        'job_comments',
        Column('id', BigInteger(), primary_key = True),
        Column('user_id', String(), index = True),
        Column('job_id', String(), index = True),
        Column('comment', String()),
        Column("created", DateTime()),
        Column("modified", DateTime())
    )

def downgrade():
    op.drop_table('job_comments')
