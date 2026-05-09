"""Initial schema.

Revision ID: 0001
Revises:
Create Date: 2026-05-09
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE event_type AS ENUM ('fact', 'measurement', 'task', 'note', 'idea')")

    op.execute("""
        CREATE TABLE users (
            id          BIGINT PRIMARY KEY,
            tz          TEXT NOT NULL DEFAULT 'UTC',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE allowed_users (
            user_id    BIGINT PRIMARY KEY REFERENCES users(id),
            added_by   BIGINT NOT NULL,
            note       TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE allowlist_log (
            id         BIGSERIAL PRIMARY KEY,
            action     TEXT NOT NULL,
            target_id  BIGINT NOT NULL,
            by_user_id BIGINT NOT NULL,
            note       TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE events (
            id           BIGSERIAL PRIMARY KEY,
            user_id      BIGINT NOT NULL REFERENCES users(id),
            type         event_type NOT NULL,
            occurred_at  TIMESTAMPTZ NOT NULL,
            raw_text     TEXT NOT NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX idx_events_user_occurred ON events(user_id, occurred_at DESC)")
    op.execute("CREATE INDEX idx_events_user_type ON events(user_id, type, occurred_at DESC)")

    op.execute("""
        CREATE TABLE entities (
            id         BIGSERIAL PRIMARY KEY,
            user_id    BIGINT NOT NULL REFERENCES users(id),
            type       event_type NOT NULL,
            name       TEXT NOT NULL,
            aliases    TEXT[] NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (user_id, type, name)
        )
    """)
    op.execute("CREATE INDEX idx_entities_lookup ON entities(user_id, type)")

    op.execute("""
        CREATE TABLE task_categories (
            id        BIGSERIAL PRIMARY KEY,
            user_id   BIGINT NOT NULL REFERENCES users(id),
            name      TEXT NOT NULL,
            aliases   TEXT[] NOT NULL DEFAULT '{}',
            is_system BOOLEAN NOT NULL DEFAULT false,
            UNIQUE (user_id, name)
        )
    """)

    op.execute("""
        CREATE TABLE fact_events (
            event_id   BIGINT PRIMARY KEY REFERENCES events(id) ON DELETE CASCADE,
            entity_id  BIGINT NOT NULL REFERENCES entities(id)
        )
    """)

    op.execute("""
        CREATE TABLE measurement_events (
            event_id   BIGINT PRIMARY KEY REFERENCES events(id) ON DELETE CASCADE,
            entity_id  BIGINT NOT NULL REFERENCES entities(id),
            value      DOUBLE PRECISION NOT NULL,
            unit       TEXT
        )
    """)
    op.execute("CREATE INDEX idx_measurements_entity ON measurement_events(entity_id)")

    op.execute("""
        CREATE TABLE task_events (
            event_id              BIGINT PRIMARY KEY REFERENCES events(id) ON DELETE CASCADE,
            text                  TEXT NOT NULL,
            category_id           BIGINT NOT NULL REFERENCES task_categories(id),
            unrecognized_reason   TEXT,
            due_date              DATE,
            priority              SMALLINT NOT NULL DEFAULT 0,
            done_at               TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX idx_tasks_open ON task_events(due_date) WHERE done_at IS NULL")
    op.execute("CREATE INDEX idx_tasks_category ON task_events(category_id) WHERE done_at IS NULL")

    op.execute("""
        CREATE TABLE note_events (
            event_id  BIGINT PRIMARY KEY REFERENCES events(id) ON DELETE CASCADE,
            text      TEXT NOT NULL
        )
    """)

    op.execute("""
        CREATE TABLE idea_events (
            event_id  BIGINT PRIMARY KEY REFERENCES events(id) ON DELETE CASCADE,
            text      TEXT NOT NULL,
            tags      TEXT[] NOT NULL DEFAULT '{}'
        )
    """)

    op.execute("""
        CREATE TABLE usage_log (
            id            BIGSERIAL PRIMARY KEY,
            user_id       BIGINT NOT NULL,
            action        TEXT NOT NULL,
            model         TEXT,
            input_tokens  INTEGER,
            output_tokens INTEGER,
            latency_ms    INTEGER,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX idx_usage_user_date ON usage_log(user_id, created_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS usage_log")
    op.execute("DROP TABLE IF EXISTS idea_events")
    op.execute("DROP TABLE IF EXISTS note_events")
    op.execute("DROP TABLE IF EXISTS task_events")
    op.execute("DROP TABLE IF EXISTS measurement_events")
    op.execute("DROP TABLE IF EXISTS fact_events")
    op.execute("DROP TABLE IF EXISTS task_categories")
    op.execute("DROP TABLE IF EXISTS entities")
    op.execute("DROP TABLE IF EXISTS events")
    op.execute("DROP TABLE IF EXISTS allowlist_log")
    op.execute("DROP TABLE IF EXISTS allowed_users")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TYPE IF EXISTS event_type")