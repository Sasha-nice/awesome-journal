"""Allow task_events.category_id to be NULL.

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE task_events ALTER COLUMN category_id DROP NOT NULL")


def downgrade() -> None:
    # Откат: вернуть NOT NULL. Если в БД уже есть таски с NULL category_id —
    # downgrade упадёт, что корректно.
    op.execute("ALTER TABLE task_events ALTER COLUMN category_id SET NOT NULL")