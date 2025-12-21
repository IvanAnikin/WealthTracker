"""add truelayer tokens to requisitions

Revision ID: 7f3c1d9b9a9a
Revises: 50e66df21da8
Create Date: 2025-12-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = '7f3c1d9b9a9a'
down_revision = '50e66df21da8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('requisitions', sa.Column('access_token', sa.String(length=2048), nullable=True))
    op.add_column('requisitions', sa.Column('refresh_token', sa.String(length=2048), nullable=True))
    op.add_column('requisitions', sa.Column('token_expires_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('requisitions', 'token_expires_at')
    op.drop_column('requisitions', 'refresh_token')
    op.drop_column('requisitions', 'access_token')
