"""Add phase and memory fields to session

Revision ID: 4396a33aeb9a
Revises: c6cda4a83ba9
Create Date: 2025-07-02 10:00:44.531632
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from app.db.models.enums import PhaseEnum

# revision identifiers, used by Alembic.
revision: str = '4396a33aeb9a'
down_revision: Union[str, None] = 'c6cda4a83ba9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create enum type first
    phase_enum = postgresql.ENUM(*[e.value for e in PhaseEnum], name="phaseenum")
    phase_enum.create(op.get_bind())

    # Then add the column using that type
    op.add_column('sessions', sa.Column('phase', phase_enum, nullable=True))
    op.add_column('sessions', sa.Column('platform_preference', sa.String(), nullable=True))
    op.add_column('sessions', sa.Column('mood_tag', sa.String(), nullable=True))
    op.add_column('sessions', sa.Column('last_recommended_game', sa.String(), nullable=True))
    op.add_column('sessions', sa.Column('rejected_games', sa.ARRAY(sa.String()), nullable=True))
    op.add_column('sessions', sa.Column('discovery_questions_asked', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('sessions', 'discovery_questions_asked')
    op.drop_column('sessions', 'rejected_games')
    op.drop_column('sessions', 'last_recommended_game')
    op.drop_column('sessions', 'mood_tag')
    op.drop_column('sessions', 'platform_preference')
    op.drop_column('sessions', 'phase')

    # Drop enum type last
    postgresql.ENUM(name="phaseenum").drop(op.get_bind())
