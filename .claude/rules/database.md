---
paths:
  - "backend/migrations/**"
  - "backend/libs/database/**"
  - "backend/scripts/**"
  - "backend/alembic.ini"
---

# Database

Schema changes are hand-written SQL, run by Alembic and mirrored by Orm classes in
`libs/database/orm/`. The SQL and the Orm classes must agree exactly, and CI's drift
check enforces that. This file owns tables, Orm classes, and migrations. How
application code uses sessions, queries, and writes is in `fastapi-structure.md` ›
Database. The procedure for making a schema change is the `db-migration` skill.

## Naming

- Every Postgres object this project creates is prefixed `pb_`: tables, enum types,
  and sequences. Python names don't carry it: `PbUserOrm` is wrong, `UserOrm` is
  right.
- Two exceptions: extensions (`citext`) aren't ours, and Alembic's `alembic_version`
  table belongs to the tooling. Both keep their own names.
- Table names are singular: `pb_user`, `pb_persona`. A many-to-many table joins both
  singular names: `pb_persona_tag`. Relationship attributes that hold collections
  stay plural: `UserOrm.personas`.
- Constraint and index names start with their table name, so they carry the prefix
  too. They follow Postgres's own generated names, and a name you write by hand must
  match the pattern:

  | Kind        | Pattern                          | Example                     |
  | ----------- | -------------------------------- | --------------------------- |
  | Primary key | `<table>_pkey`                   | `pb_user_pkey`              |
  | Unique      | `<table>_<columns>_key`          | `pb_user_identity_key`      |
  | Foreign key | `<table>_<column>_fkey`          | `pb_user_created_by_id_fkey` |
  | Index       | `<table>_<columns>_idx`          | `pb_persona_created_by_id_created_at_idx` |
  | Check       | `<table>_<name>_check`           | `pb_persona_name_check`     |

- Columns ending `_id` are `BIGINT` foreign keys. A provider's or third party's
  identifier never takes that suffix: `provider_subject`, not `provider_id`.
- Boolean columns start with `is_` (`python-naming.md` › Variables): `is_active`,
  `is_email_verified`.

## Tables

### Shared columns

Every table has these columns. `BaseOrm` in `libs/database/base.py` maps them, so an Orm
class never redeclares them.

| Column          | SQL                                                          | Orm                        | Notes |
| --------------- | ------------------------------------------------------------ | -------------------------- | ----- |
| `id`            | `BIGINT GENERATED ALWAYS AS IDENTITY`                        | `Mapped[int]`              | Primary key. Never leaves the backend |
| `identity`      | `UUID NOT NULL DEFAULT gen_random_uuid()`                    | `Mapped[UUID]`             | Unique. The ID the API exposes |
| `created_at`    | `TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc')`      | `Mapped[datetime]`         | |
| `updated_at`    | `TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc')`      | `Mapped[datetime]`         | SQLAlchemy `onupdate` sets it from the database clock on every update |
| `deleted_at`    | `TIMESTAMP`                                                  | `Mapped[datetime \| None]` | On `SoftDeleteMixin`, which `BaseOrm` inherits |
| `created_by_id` | `BIGINT NOT NULL`, FK `pb_user (id)`                         | `Mapped[int]`              | |
| `updated_by_id` | `BIGINT NOT NULL`, FK `pb_user (id)`                         | `Mapped[int]`              | |
| `deleted_by_id` | `BIGINT`, FK `pb_user (id)`                                  | `Mapped[int \| None]`      | |

`pb_user` is the one exception: its `created_by_id` and `updated_by_id` are nullable,
since a person signing up has no creator. `UserOrm` redeclares both.

A foreign key has no `ON DELETE` clause, in the SQL or as `ondelete=` in the Orm.
Postgres then blocks deleting a referenced row. Rows are soft-deleted, so a real delete
is rare and should fail loudly rather than quietly remove or unlink data. Add a clause
only for one of these reasons:

- `CASCADE` on a child that only exists as part of its parent:
  `pb_generate_text_step.run_id`, `pb_user_auth_provider.user_id`.
- `SET NULL` on a log that must outlive what it references: `pb_llm_call.run_id` and
  `step_id`.

### Table shape

Every `CREATE TABLE` lists the shared columns in this order:

```sql
-- migrations/sql/pb_persona/0001_create_pb_persona.up.sql
CREATE TABLE pb_persona (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identity UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    name TEXT NOT NULL,
    bio TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    deleted_at TIMESTAMP,
    created_by_id BIGINT NOT NULL REFERENCES pb_user (id),
    updated_by_id BIGINT NOT NULL REFERENCES pb_user (id),
    deleted_by_id BIGINT REFERENCES pb_user (id)
);

CREATE INDEX pb_persona_created_by_id_created_at_idx
    ON pb_persona (created_by_id, created_at DESC);
```

- Table-specific columns go between `identity` and `created_at`.
- A constraint on a single column is written inline and unnamed: `PRIMARY KEY`,
  `UNIQUE`, `REFERENCES pb_user (id)`, `CHECK (...)`. Postgres names
  it `<table>_pkey`, `<table>_<column>_key`, or `<table>_<column>_fkey`, which is the
  naming convention, and the drift check confirms the names match.
- A constraint spanning several columns goes at table level, named:
  `CONSTRAINT pb_persona_tag_persona_id_tag_id_key UNIQUE (persona_id, tag_id)`.
- Postgres truncates generated names longer than 63 characters, and SQLAlchemy
  shortens them differently. If a table and column name are that long, name the
  constraint explicitly in both the SQL and the Orm class.
- Text is `TEXT`, never `VARCHAR(n)`. Case-insensitive text is `CITEXT`.
- Postgres doesn't index foreign keys. Add an index for each one you query by.
- A unique constraint on a soft-deletable table is usually a partial unique index,
  `CREATE UNIQUE INDEX ... WHERE deleted_at IS NULL`, so a soft-deleted row doesn't
  block a new one. An `ON CONFLICT` upsert against it must repeat the condition.

### Timestamps

- Timestamps are `TIMESTAMP` without time zone and always hold UTC. Never
  `TIMESTAMPTZ`.
- `Mapped[datetime]` maps to `UtcDateTime` (`libs/database/column_types.py`), which
  stores naive UTC and returns aware UTC. Python code only ever handles aware UTC
  datetimes. A naive datetime raises at flush.
- Every "now" a query compares with or a write stores comes from the database clock,
  never the app server's `datetime.now(UTC)`: servers' clocks drift apart, and the
  database's is the one they all share. `libs/database/clock.py` builds it as SQL,
  written into the statement itself:
  - `build_utc_now_sql()` inside a query or an `update()`:
    `.where(GenerateTextRunOrm.lease_expires_at <= build_utc_now_sql())`,
    `.values(last_login_at=build_utc_now_sql())`. `build_utc_now_plus_sql(seconds)`
    is a time that far ahead, such as a lease expiry.
  - `updated_at` is set by `BaseOrm` from the same clock and fetched back with
    `RETURNING`.
  - Never assign `build_utc_now_sql()` to an Orm attribute: async code can't read the
    attribute back until the row is reloaded. A write that sets Orm attributes and
    flushes still reads `datetime.now(UTC)` for now, marked `TODO(db-clock)`, until it
    becomes an `update()` or `insert()` statement (`plans/plan.md`).
- A service that writes a time takes none from its caller.
- Inside one transaction the database clock is the transaction's start time, so every
  time one transaction writes is the same.
- `datetime.now(UTC)` is only for a time that never reaches the database, such as
  checking a third-party token's expiry. A duration uses `DateTimeUtils`' monotonic
  clock.
- No database triggers. SQLAlchemy sets `updated_at` on every Orm update and
  `update()` statement, so only an `UPDATE` written in raw SQL, like a backfill, sets
  `updated_at` itself.

### Soft delete

- Rows are soft-deleted: set `deleted_at` and `deleted_by_id`. Never `DELETE` in
  application code.
- Sessions from `create_db_session_factory()` (`libs/database/session.py`) add
  `deleted_at IS NULL` to every ORM select, including relationship loads. The rule
  targets `SoftDeleteMixin`, because SQLAlchemy can't apply loader criteria to a
  `DeclarativeBase` directly.
- Raw SQL and Core statements aren't filtered.
- How to read soft-deleted rows on purpose isn't settled yet. Decide it with the first
  feature that needs to, and record it here.

### Enums

Postgres enum labels are `UPPER_SNAKE` and match the Python `StrEnum` members
exactly. That holds for our own enums only; an enum that mirrors an outside API's values
is never a column (`python-naming.md` › Enums). The type is `pb_` plus the class name in
snake_case: `AuthProviderType` → `pb_auth_provider_type`.

```sql
CREATE TYPE pb_auth_provider_type AS ENUM ('GOOGLE');
```

- The Orm column names the type: `mapped_column(Enum(AuthProviderType, name="pb_auth_provider_type"))`.
  The `StrEnum` lives in the owning domain's `libs/<domain>/types.py`.
- Adding a member goes in its own revision:
  `ALTER TYPE pb_auth_provider_type ADD VALUE 'GITHUB'`, in the same commit as the
  Python change.
- Removing a member isn't supported by Postgres. It takes a new type, a column
  migration, and dropping the old type.
- The `.down.sql` for a table using a type drops the type after the table.

## Orm classes

Every table has one module in `libs/database/orm/`, regardless of which domain uses
it. `libs/database/orm/__init__.py` imports every module in the package, which is what
guarantees all mappers are registered before configuration.

```python
# libs/database/orm/__init__.py
from libs.database.orm.persona import PersonaOrm
from libs.database.orm.user import UserOrm

__all__ = ["PersonaOrm", "UserOrm"]
```

- Every Orm class extends `BaseOrm`. `BaseOrm` maps annotations to column types:
  `str` → `TEXT`, `datetime` → `UtcDateTime`, `UUID` → `UUID`. Declare `CITEXT`,
  `BIGINT` foreign keys, and enums explicitly.
- Nullability comes from the annotation: `Mapped[str | None]` is nullable. Server
  defaults the SQL declares are mirrored with `server_default` (`false()`, `true()`,
  `text(...)`).
- Indexes and partial unique indexes are declared in `__table_args__` with the exact
  name the SQL uses:
  `Index("pb_user_email_idx", "email", unique=True, postgresql_where=text("deleted_at IS NULL"))`.
- Many-to-many association tables go in `libs/database/orm/associations.py`.
- `libs/database/base.py`, `session.py`, `column_types.py`, and `constants.py` are
  setup files. Changing them is a deliberate design change, not part of adding a table.

### References between tables

Use direct symbols where import order allows:

```python
# libs/database/orm/generate_text_step.py
class GenerateTextStepOrm(BaseOrm):
    __tablename__ = "pb_generate_text_step"

    run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(GenerateTextRunOrm.id))
    run: Mapped[GenerateTextRunOrm] = relationship(back_populates="steps")
```

- `ForeignKey(GenerateTextRunOrm.id)`, never `ForeignKey("pb_generate_text_run.id")`.
- `__tablename__` and the `back_populates` attribute name are the only permitted loose
  strings, with one exception: `ForeignKey("pb_user.id")` on `BaseOrm`'s audit columns and
  `UserOrm`'s own overrides of them, because `UserOrm` extends `BaseOrm` and can't be
  imported there.
- Add a relationship only in the direction a query uses. A one-way relationship takes
  no `back_populates` and no quoted class name: `BlogPostOrm.content_item:
  Mapped[ContentItemOrm] = relationship()`.
- A quoted class name in `relationship()` or `Mapped[...]` is allowed on **one** side
  of a mutual relationship only. Put the forward reference on the parent
  (`GenerateTextRunOrm.steps`) and the concrete import on the child.
- The quoted side still imports its target under `if TYPE_CHECKING:`, so type checkers
  resolve it and ruff doesn't strip the quotes as an unnecessary forward reference:

```python
# libs/database/orm/generate_text_run.py
if TYPE_CHECKING:
    from libs.database.orm.generate_text_step import GenerateTextStepOrm


class GenerateTextRunOrm(BaseOrm):
    steps: Mapped[list["GenerateTextStepOrm"]] = relationship(back_populates="run")
```

## Migrations

Migrations are raw SQL in `backend/migrations/`. They never import application code,
and application code never imports them.

- Alembic is a runner only. **Never** `alembic revision --autogenerate`.
- `migrations/env.py` imports no `BaseOrm` or Orm module and has no `target_metadata`.
  It reads `DATABASE_URL` from the environment, loading `.env` with python-dotenv;
  real environment variables win.
- Every schema change produces three things in the same commit: the `.up.sql` and
  `.down.sql` pair, the revision that runs them, and the matching Orm change. Missing
  the Orm change is the most common failure.

### Layout

```
backend/migrations/
├── env.py
├── migration_runner.py
├── script.py.mako
├── revisions/
│   ├── 20260917_1527_enable_citext.py
│   ├── 20260917_1528_create_user_tables.py
│   └── 20260917_1529_insert_system_user.py
└── sql/
    ├── extensions/                 # CREATE EXTENSION files
    │   ├── 0001_enable_citext.up.sql
    │   └── 0001_enable_citext.down.sql
    └── pb_user/                    # one folder per table, named exactly as the table
        ├── 0001_create_pb_user.up.sql
        ├── 0001_create_pb_user.down.sql
        ├── 0002_insert_system_user.up.sql
        └── 0002_insert_system_user.down.sql
```

- SQL files are `<nnnn>_<what_it_does>.<up|down>.sql`, zero-padded to four, in the
  folder of the table they change. The verb describes the change:
  `create_pb_user`, `add_display_name`, `backfill_persona_slug`, `drop_legacy_token`.
- SQL that isn't about one table goes in a named folder: extensions in
  `sql/extensions/`.
- The numeric prefix orders changes within one folder, for human reading only.
  Ordering across tables is Alembic's `down_revision` chain.
- A revision is a unit that ships and rolls back together, usually one feature's
  tables. Each table's SQL goes in its own folder, and the revision runs the files in
  dependency order.
- Extensions get their own revision, since several features depend on them. Seed rows
  (the system user) get their own revision, after the tables they fill.
- One logical change per `.up.sql` file.

### Revisions

Revision files are `<YYYYMMDD>_<HHMM>_<slug>.py`, from `file_template` in
`alembic.ini`. The revision id is the same timestamp in UTC, passed explicitly:

```bash
uv run alembic revision --rev-id 20260917_1528 -m create_user_tables
```

The wrapper names SQL files and contains no SQL:

```python
# revisions/20260917_1528_create_user_tables.py
from migration_runner import MigrationRunner

revision = "20260917_1528"
down_revision = "20260917_1527"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_user/0001_create_pb_user.up.sql")
    MIGRATION_RUNNER.run_transactional(
        "pb_user_auth_provider/0001_create_pb_user_auth_provider.up.sql"
    )


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional(
        "pb_user_auth_provider/0001_create_pb_user_auth_provider.down.sql"
    )
    MIGRATION_RUNNER.run_transactional("pb_user/0001_create_pb_user.down.sql")
```

- `upgrade()` runs the `.up.sql` files it names; `downgrade()` runs the matching
  `.down.sql` files in reverse order. Nothing is inferred from filenames.
- The chain is append-only. `down_revision` points at the current head
  (`uv run alembic heads`). Never insert a revision between two that have already run;
  a change to an applied migration is a new migration.
- `alembic.ini` sets `prepend_sys_path` to `migrations/`, so revisions import
  `migration_runner` as a top-level module and `migrations/` stays out of the package
  tree.
- Every migration ships a `.down.sql`. If a change is irreversible, the down file
  carries a comment saying so plus whatever schema-only reversal it can manage. It is
  never omitted.

### Transactional vs non-transactional

Each revision runs in its own transaction (`transaction_per_migration=True`).
`MigrationRunner` has two methods. Pick deliberately.

- **`run_transactional(path)`** is the default. It splits the file with `sqlparse` and
  runs every statement inside the revision's transaction. In Postgres that covers
  nearly everything, including DDL.
- **`run_non_transactional(path)`** runs the file in Alembic's `autocommit_block()`,
  which commits the revision's transaction so far, runs the statement with autocommit,
  and opens a fresh transaction for the rest. It raises if the file holds more than one
  statement, because a partial failure outside a transaction leaves the schema
  half-changed. Use it only for statements Postgres
  refuses to run in a transaction: `CREATE INDEX CONCURRENTLY`,
  `DROP INDEX CONCURRENTLY`, `REINDEX CONCURRENTLY`, `VACUUM`.
  - A non-transactional statement gets its own file and its own revision. Never
    bundle a concurrent index with other changes.
  - Name those files for what they are: `0003_add_email_index_concurrently.up.sql`.
  - The `.down.sql` for a concurrent index is also concurrent, and also alone.

The runner executes through `exec_driver_sql()`, so SQL reaches Postgres untouched.
Never switch it to `op.execute()`, which parses any `:word` in the SQL as a bind
parameter. Never split SQL on `;` by hand: semicolons appear inside string literals,
comments, and function bodies.

### Data migrations

- Backfills go in their own `.up.sql` file, separate from the DDL that created the
  column, so a slow backfill can be rerun or skipped on its own.
- The `.down.sql` for a backfill is usually a comment explaining that the data change
  isn't reversible.
- A backfill `UPDATE` sets `updated_at` itself (see Timestamps).
- Batch anything touching a large table. A single `UPDATE` over every row holds locks
  for its whole duration.

## Drift check

CI applies all migrations to an empty database, then runs:

```bash
uv run python -m scripts.db.check_schema_drift
```

The script compares the database with `BaseOrm.metadata` through Alembic's
`compare_metadata`, ignoring `alembic_version`, and exits non-zero on any difference:
a column, type, nullability, index, or constraint that doesn't match. Autogenerate is a
detector that fails the build, never a generator that writes files.

Scripts in `backend/scripts/` may import `libs/` and run as modules from `backend/`
(`python -m scripts.<name>`). Nothing imports from `scripts/`. The folder also holds
shell scripts, which are run directly rather than as modules: see `CLAUDE.md` ›
Commands for Tyler to run.
