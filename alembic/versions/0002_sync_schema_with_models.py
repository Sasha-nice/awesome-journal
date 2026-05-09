"""Sync schema with parser models.

- idea_events: drop tags column (idea = только text)
- task_events: drop unrecognized_reason
- task_events: rename text → title

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE idea_events DROP COLUMN tags")
    op.execute("ALTER TABLE task_events DROP COLUMN unrecognized_reason")
    op.execute("ALTER TABLE task_events RENAME COLUMN text TO title")


def downgrade() -> None:
    op.execute("ALTER TABLE task_events RENAME COLUMN title TO text")
    op.execute("ALTER TABLE task_events ADD COLUMN unrecognized_reason TEXT")
    op.execute("ALTER TABLE idea_events ADD COLUMN tags TEXT[] NOT NULL DEFAULT '{}'")