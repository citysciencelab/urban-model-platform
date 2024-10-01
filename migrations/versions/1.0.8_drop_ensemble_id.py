"""Drop ensemble id

Revision ID: 1.0.8
Revises:
Create Date: 2024-10-01 14:00

"""

from alembic import op
from sqlalchemy import BigInteger, Column

revision = "1.0.8"
down_revision = "1.0.7"
branch_labels = "drop_ensemble_id"
depends_on = "1.0.7"

def upgrade():
    op.drop_column('jobs', 'ensemble_id')

def downgrade():
    op.add_column('jobs', Column('ensemble_id', BigInteger(), index = True))
