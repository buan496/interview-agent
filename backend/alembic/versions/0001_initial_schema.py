from __future__ import annotations

from alembic import op


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def _execute_many(sql: str) -> None:
    for statement in sql.split(";"):
        statement = statement.strip()
        if statement:
            op.execute(statement)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    _execute_many(
        """
        CREATE TABLE companies (
          id          SERIAL PRIMARY KEY,
          name        VARCHAR(100) NOT NULL UNIQUE,
          name_en     VARCHAR(100),
          region      VARCHAR(20) NOT NULL DEFAULT 'CN',
          tier        SMALLINT DEFAULT 1,
          logo_url    TEXT
        );

        CREATE TABLE positions (
          id    SERIAL PRIMARY KEY,
          name  VARCHAR(50) NOT NULL UNIQUE
        );

        CREATE TABLE tags (
          id        SERIAL PRIMARY KEY,
          name      VARCHAR(50) NOT NULL UNIQUE,
          category  VARCHAR(30)
        );

        CREATE TABLE questions (
          id            BIGSERIAL PRIMARY KEY,
          title         VARCHAR(300) NOT NULL,
          body          TEXT,
          answer_key    TEXT NOT NULL,
          difficulty    SMALLINT NOT NULL DEFAULT 3,
          qtype         VARCHAR(20) NOT NULL,
          source_type   VARCHAR(20) NOT NULL,
          source_note   TEXT,
          company_id    INT REFERENCES companies(id),
          position_id   INT REFERENCES positions(id),
          embedding     vector(1024),
          status        VARCHAR(15) DEFAULT 'active',
          ask_count     INT DEFAULT 0,
          created_at    TIMESTAMPTZ DEFAULT now()
        );
        CREATE INDEX idx_q_company_pos ON questions(company_id, position_id, status);
        CREATE INDEX idx_q_embedding ON questions USING hnsw (embedding vector_cosine_ops);

        CREATE TABLE question_tags (
          question_id BIGINT REFERENCES questions(id) ON DELETE CASCADE,
          tag_id      INT REFERENCES tags(id),
          PRIMARY KEY (question_id, tag_id)
        );

        CREATE TABLE users (
          id            BIGSERIAL PRIMARY KEY,
          phone         VARCHAR(20) UNIQUE,
          nickname      VARCHAR(50),
          target_company_id  INT REFERENCES companies(id),
          target_position_id INT REFERENCES positions(id),
          level         VARCHAR(20) DEFAULT 'junior',
          created_at    TIMESTAMPTZ DEFAULT now()
        );

        CREATE TABLE sessions (
          id          BIGSERIAL PRIMARY KEY,
          user_id     BIGINT NOT NULL REFERENCES users(id),
          mode        VARCHAR(15) NOT NULL,
          company_id  INT REFERENCES companies(id),
          position_id INT REFERENCES positions(id),
          status      VARCHAR(15) DEFAULT 'ongoing',
          report      JSONB,
          started_at  TIMESTAMPTZ DEFAULT now(),
          ended_at    TIMESTAMPTZ
        );

        CREATE TABLE session_questions (
          id           BIGSERIAL PRIMARY KEY,
          session_id   BIGINT NOT NULL REFERENCES sessions(id),
          question_id  BIGINT NOT NULL REFERENCES questions(id),
          order_no     SMALLINT NOT NULL,
          final_score  SMALLINT,
          mastery      VARCHAR(10),
          finished_at  TIMESTAMPTZ
        );

        CREATE TABLE messages (
          id           BIGSERIAL PRIMARY KEY,
          sq_id        BIGINT NOT NULL REFERENCES session_questions(id),
          role         VARCHAR(12) NOT NULL,
          content      TEXT NOT NULL,
          msg_type     VARCHAR(15) NOT NULL,
          eval_json    JSONB,
          created_at   TIMESTAMPTZ DEFAULT now()
        );
        CREATE INDEX idx_msg_sq ON messages(sq_id, id);

        CREATE TABLE wrong_book (
          user_id     BIGINT REFERENCES users(id),
          question_id BIGINT REFERENCES questions(id),
          last_score  SMALLINT,
          fail_count  SMALLINT DEFAULT 1,
          next_review DATE,
          PRIMARY KEY (user_id, question_id)
        );

        CREATE TABLE user_tag_stats (
          user_id   BIGINT REFERENCES users(id),
          tag_id    INT REFERENCES tags(id),
          attempts  INT DEFAULT 0,
          avg_score NUMERIC(5,2) DEFAULT 0,
          PRIMARY KEY (user_id, tag_id)
        );
        """
    )


def downgrade() -> None:
    _execute_many(
        """
        DROP TABLE IF EXISTS user_tag_stats;
        DROP TABLE IF EXISTS wrong_book;
        DROP TABLE IF EXISTS messages;
        DROP TABLE IF EXISTS session_questions;
        DROP TABLE IF EXISTS sessions;
        DROP TABLE IF EXISTS users;
        DROP TABLE IF EXISTS question_tags;
        DROP INDEX IF EXISTS idx_q_embedding;
        DROP INDEX IF EXISTS idx_q_company_pos;
        DROP TABLE IF EXISTS questions;
        DROP TABLE IF EXISTS tags;
        DROP TABLE IF EXISTS positions;
        DROP TABLE IF EXISTS companies;
        """
    )
