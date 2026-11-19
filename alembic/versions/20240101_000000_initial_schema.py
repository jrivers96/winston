"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Issues table
    op.create_table(
        'issues',
        sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('id', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('index_id', sa.String(length=255), nullable=True),
        sa.Column('environment', sa.String(length=100), nullable=True),
        sa.Column('affected_dates', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('state', sa.String(length=50), nullable=False),
        sa.Column('state_changed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('severity', sa.String(length=50), nullable=True),
        sa.Column('impact_summary', sa.Text(), nullable=True),
        sa.Column('affected_executions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('evidence_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('completion_criteria', sa.Text(), nullable=True),
        sa.Column('previous_issue_id', sa.String(length=255), nullable=True),
        sa.Column('recurrence_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('fingerprint', sa.String(length=255), nullable=True),
        sa.Column('extra_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.PrimaryKeyConstraint('pk')
    )
    op.create_index('ix_issues_id', 'issues', ['id'], unique=True)
    op.create_index('ix_issues_index_id', 'issues', ['index_id'])
    op.create_index('ix_issues_state', 'issues', ['state'])
    op.create_index('ix_issues_fingerprint', 'issues', ['fingerprint'])

    # Obligations table
    op.create_table(
        'obligations',
        sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('id', sa.String(length=255), nullable=False),
        sa.Column('issue_id', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('action_type', sa.String(length=100), nullable=False),
        sa.Column('owner', sa.String(length=255), nullable=True),
        sa.Column('state', sa.String(length=50), nullable=False),
        sa.Column('state_changed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('wake_condition', sa.Text(), nullable=True),
        sa.Column('due_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('progress_notes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=True),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('evidence_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('extra_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.ForeignKeyConstraint(['issue_id'], ['issues.id']),
        sa.PrimaryKeyConstraint('pk')
    )
    op.create_index('ix_obligations_id', 'obligations', ['id'], unique=True)
    op.create_index('ix_obligations_issue_id', 'obligations', ['issue_id'])
    op.create_index('ix_obligations_state', 'obligations', ['state'])

    # Executions table
    op.create_table(
        'executions',
        sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('id', sa.String(length=255), nullable=False),
        sa.Column('attempt_id', sa.String(length=255), nullable=True),
        sa.Column('index_id', sa.String(length=255), nullable=False),
        sa.Column('environment', sa.String(length=100), nullable=False),
        sa.Column('business_date', sa.String(length=10), nullable=False),
        sa.Column('stage', sa.String(length=100), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('status_message', sa.Text(), nullable=True),
        sa.Column('input_manifest_id', sa.String(length=255), nullable=True),
        sa.Column('code_manifest_id', sa.String(length=255), nullable=True),
        sa.Column('state_artifact_id', sa.String(length=255), nullable=True),
        sa.Column('output_artifact_id', sa.String(length=255), nullable=True),
        sa.Column('validation_status', sa.String(length=50), nullable=True),
        sa.Column('validation_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('extra_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('pk'),
        sa.UniqueConstraint('index_id', 'environment', 'business_date', 'attempt_id', name='uq_execution_identity')
    )
    op.create_index('ix_executions_id', 'executions', ['id'], unique=True)
    op.create_index('ix_executions_index_id', 'executions', ['index_id'])
    op.create_index('ix_executions_environment', 'executions', ['environment'])
    op.create_index('ix_executions_business_date', 'executions', ['business_date'])
    op.create_index('ix_executions_status', 'executions', ['status'])

    # Artifacts table
    op.create_table(
        'artifacts',
        sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('id', sa.String(length=255), nullable=False),
        sa.Column('execution_id', sa.String(length=255), nullable=False),
        sa.Column('artifact_type', sa.String(length=50), nullable=False),
        sa.Column('schema_id', sa.String(length=255), nullable=True),
        sa.Column('schema_version', sa.String(length=50), nullable=True),
        sa.Column('is_available', sa.Boolean(), nullable=True),
        sa.Column('availability_note', sa.Text(), nullable=True),
        sa.Column('byte_hash', sa.String(length=64), nullable=True),
        sa.Column('semantic_hash', sa.String(length=64), nullable=True),
        sa.Column('storage_ref', sa.String(length=500), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('content', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_sample', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('pk')
    )
    op.create_index('ix_artifacts_id', 'artifacts', ['id'], unique=True)
    op.create_index('ix_artifacts_execution_id', 'artifacts', ['execution_id'])

    # Repositories table
    op.create_table(
        'repositories',
        sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('id', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('location_type', sa.String(length=50), nullable=False),
        sa.Column('location_path', sa.String(length=500), nullable=True),
        sa.Column('location_origin', sa.String(length=500), nullable=True),
        sa.Column('credential_provider', sa.String(length=255), nullable=True),
        sa.Column('role', sa.String(length=100), nullable=False),
        sa.Column('owner', sa.String(length=255), nullable=True),
        sa.Column('languages', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('allowed_paths', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('excluded_paths', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('access_scope', sa.String(length=50), nullable=True),
        sa.Column('retrieval_budget_mb', sa.Integer(), nullable=True),
        sa.Column('cache_budget_mb', sa.Integer(), nullable=True),
        sa.Column('default_branch', sa.String(length=255), nullable=True),
        sa.Column('registration_source', sa.String(length=255), nullable=True),
        sa.Column('registry_revision', sa.String(length=255), nullable=True),
        sa.Column('sync_status', sa.String(length=50), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_accessible', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('pk')
    )
    op.create_index('ix_repositories_id', 'repositories', ['id'], unique=True)

    # Audit events table
    op.create_table(
        'audit_events',
        sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('entity_type', sa.String(length=100), nullable=False),
        sa.Column('entity_id', sa.String(length=255), nullable=False),
        sa.Column('actor', sa.String(length=255), nullable=False),
        sa.Column('old_state', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_state', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('pk')
    )
    op.create_index('ix_audit_events_event_type', 'audit_events', ['event_type'])
    op.create_index('ix_audit_events_entity_type', 'audit_events', ['entity_type'])
    op.create_index('ix_audit_events_entity_id', 'audit_events', ['entity_id'])
    op.create_index('ix_audit_events_occurred_at', 'audit_events', ['occurred_at'])

    # Collection receipts table
    op.create_table(
        'collection_receipts',
        sa.Column('pk', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('id', sa.String(length=255), nullable=False),
        sa.Column('source_type', sa.String(length=100), nullable=False),
        sa.Column('source_scope', sa.Text(), nullable=False),
        sa.Column('external_statement_id', sa.String(length=255), nullable=True),
        sa.Column('query_template_id', sa.String(length=255), nullable=True),
        sa.Column('requested_time_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('requested_time_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_time_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_time_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('collection_started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('collection_completed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('truncated', sa.Boolean(), nullable=True),
        sa.Column('warnings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('evidence_artifact_id', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('pk')
    )
    op.create_index('ix_collection_receipts_id', 'collection_receipts', ['id'], unique=True)
    op.create_index('ix_collection_receipts_source_type', 'collection_receipts', ['source_type'])


def downgrade() -> None:
    op.drop_table('collection_receipts')
    op.drop_table('audit_events')
    op.drop_table('repositories')
    op.drop_table('artifacts')
    op.drop_table('executions')
    op.drop_table('obligations')
    op.drop_table('issues')
