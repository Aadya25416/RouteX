"""phase2_incident_management

Revision ID: f465174fcaeb
Revises: c47927b88b8b
Create Date: 2026-10-12 20:18:06.977388

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f465174fcaeb'
down_revision: Union[str, None] = 'c47927b88b8b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create incident_road_associations table
    op.create_table(
        'incident_road_associations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('incident_id', sa.UUID(), nullable=False),
        sa.Column('road_segment_id', sa.String(length=64), nullable=False),
        sa.Column('association_type', sa.String(length=30), nullable=False, server_default='SUGGESTED'),
        sa.Column('assessed_impact', sa.String(length=30), nullable=True),
        sa.Column('distance_m', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['road_segment_id'], ['road_segments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('incident_id', 'road_segment_id', name='uq_incident_road_segment'),
    )
    op.create_index(op.f('ix_incident_road_associations_incident_id'), 'incident_road_associations', ['incident_id'], unique=False)
    op.create_index(op.f('ix_incident_road_associations_road_segment_id'), 'incident_road_associations', ['road_segment_id'], unique=False)
    op.create_index(op.f('ix_incident_road_associations_association_type'), 'incident_road_associations', ['association_type'], unique=False)
    op.create_index(op.f('ix_incident_road_associations_assessed_impact'), 'incident_road_associations', ['assessed_impact'], unique=False)

    # 2. Add Phase 2 columns to incident_evidence
    op.add_column('incident_evidence', sa.Column('original_filename', sa.String(length=255), nullable=True))
    op.add_column('incident_evidence', sa.Column('stored_filename', sa.String(length=255), nullable=True))
    op.add_column('incident_evidence', sa.Column('media_type', sa.String(length=100), nullable=True))
    op.add_column('incident_evidence', sa.Column('file_size_bytes', sa.BigInteger(), nullable=True))
    op.add_column('incident_evidence', sa.Column('processing_status', sa.String(length=50), nullable=False, server_default='PENDING', comment='PENDING, PROCESSED, FAILED'))
    op.add_column('incident_evidence', sa.Column('model_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # 3. Add Phase 2 columns to incidents
    op.add_column('incidents', sa.Column('source', sa.String(length=50), nullable=False, server_default='FIELD_REPORT'))
    op.add_column('incidents', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('incidents', sa.Column('reviewer_id', sa.UUID(), nullable=True))
    op.add_column('incidents', sa.Column('review_notes', sa.Text(), nullable=True))
    op.add_column('incidents', sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('incidents', sa.Column('resolved_by', sa.UUID(), nullable=True))
    op.add_column('incidents', sa.Column('resolution_notes', sa.Text(), nullable=True))

    op.alter_column(
        'incidents',
        'status',
        existing_type=sa.VARCHAR(length=20),
        type_=sa.String(length=30),
        server_default='SUBMITTED',
        comment='SUBMITTED, UNDER_REVIEW, CONFIRMED, REJECTED, DUPLICATE, RESOLVED',
        existing_comment='reported, confirmed, rejected, resolved',
        existing_nullable=False,
    )

    op.create_foreign_key('fk_incidents_reviewer_id_users', 'incidents', 'users', ['reviewer_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_incidents_resolved_by_users', 'incidents', 'users', ['resolved_by'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_incidents_resolved_by_users', 'incidents', type_='foreignkey')
    op.drop_constraint('fk_incidents_reviewer_id_users', 'incidents', type_='foreignkey')

    op.alter_column(
        'incidents',
        'status',
        existing_type=sa.String(length=30),
        type_=sa.VARCHAR(length=20),
        server_default='reported',
        comment='reported, confirmed, rejected, resolved',
        existing_comment='SUBMITTED, UNDER_REVIEW, CONFIRMED, REJECTED, DUPLICATE, RESOLVED',
        existing_nullable=False,
    )

    op.drop_column('incidents', 'resolution_notes')
    op.drop_column('incidents', 'resolved_by')
    op.drop_column('incidents', 'resolved_at')
    op.drop_column('incidents', 'review_notes')
    op.drop_column('incidents', 'reviewer_id')
    op.drop_column('incidents', 'reviewed_at')
    op.drop_column('incidents', 'source')

    op.drop_column('incident_evidence', 'model_metadata')
    op.drop_column('incident_evidence', 'processing_status')
    op.drop_column('incident_evidence', 'file_size_bytes')
    op.drop_column('incident_evidence', 'media_type')
    op.drop_column('incident_evidence', 'stored_filename')
    op.drop_column('incident_evidence', 'original_filename')

    op.drop_index(op.f('ix_incident_road_associations_assessed_impact'), table_name='incident_road_associations')
    op.drop_index(op.f('ix_incident_road_associations_association_type'), table_name='incident_road_associations')
    op.drop_index(op.f('ix_incident_road_associations_road_segment_id'), table_name='incident_road_associations')
    op.drop_index(op.f('ix_incident_road_associations_incident_id'), table_name='incident_road_associations')
    op.drop_table('incident_road_associations')
