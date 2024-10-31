"""Add hash

Revision ID: 1.0.11
Revises:
Create Date: 2024-10-02 14:00

"""

from alembic import op
from sqlalchemy import Column, String

revision = "1.0.11"
down_revision = "1.0.10"
branch_labels = "add_hash"
depends_on = "1.0.10"

def upgrade():
    op.add_column('jobs', Column('hash', String(), index = True))
    op.execute('create extension pgcrypto')
    op.execute("update jobs set hash = encode(sha512((parameters :: text || process_version || user_id) :: bytea), 'base64')")

def downgrade():
    op.drop_column('jobs', 'hash')
    op.execute('drop extension pgcrypto')
