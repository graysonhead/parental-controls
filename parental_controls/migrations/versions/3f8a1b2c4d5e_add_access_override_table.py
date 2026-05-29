"""add access_override table

Revision ID: 3f8a1b2c4d5e
Revises: fb55b5240552
Create Date: 2026-05-29 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = '3f8a1b2c4d5e'
down_revision: Union[str, Sequence[str], None] = 'fb55b5240552'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'accessoverride',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('child_id', sa.Integer(), nullable=False),
        sa.Column('override_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('reason', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['child_id'], ['child.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_accessoverride_child_id'), 'accessoverride', ['child_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_accessoverride_child_id'), table_name='accessoverride')
    op.drop_table('accessoverride')
