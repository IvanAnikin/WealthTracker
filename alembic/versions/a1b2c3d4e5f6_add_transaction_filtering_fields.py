"""Add transaction filtering fields

Revision ID: a1b2c3d4e5f6
Revises: 3891303f5301, d14df1218d8f
Create Date: 2025-12-21 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = ('3891303f5301', 'd14df1218d8f')
branch_labels = None
depends_on = None


def upgrade():
    # Add account_purpose column to accounts table
    op.add_column('accounts', sa.Column('account_purpose', sa.String(50), nullable=False, server_default='spending'))
    
    # Add is_internal_transfer column to transactions table
    op.add_column('transactions', sa.Column('is_internal_transfer', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    op.drop_column('transactions', 'is_internal_transfer')
    op.drop_column('accounts', 'account_purpose')
