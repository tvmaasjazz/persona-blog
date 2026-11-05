---
paths:
  - "backend/migrations/**"
  - "backend/libs/database/**"
  - "backend/scripts/db/**"
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
- Boolean columns start with `is_` (`python-naming.md` › Variables).

## Tables

### Shared columns

Every table has these columns. `BaseOrm` in `libs/database/base.py` maps them, so an Orm
class never redeclares them.

| Column          | SQL                                                          | Orm                        | Notes |
| --------------- | ------------------------------------------------------------ | -------------------------- | ----- |
| `id`            | `BIGINT GENERATED ALWAYS AS IDENTITY`                        | `Mapped[int]`              | Primary key. Never leaves the backend |
| `identity`      | `UUID NOT NULL DEFAULT gen_random_uuid()`                    | `Mapped[UUID]`             | Unique. The ID the API exposes |
| `created_at`    | `TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc')`      | `Mapped[datetime]`         | |
| `updated_at`    | `TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc')`      | `Mapped[datetime]`         | `BaseOrm`'s `onupdate` sets it (Timestamps) |
| `deleted_at`    | `TIMESTAMP`                                                  | `Mapped[datetime \| None]` | On `SoftDeleteMixin`, which `BaseOrm` inherits |
| `created_by_id` | `BIGINT NOT NULL`, FK `pb_user (id)`                         | `Mapped[int]`              | |
| `updated_by_id` | `BIGINT NOT NULL`, FK `pb_user (id)`                         | `Mapped[int]`              | |
| `deleted_by_id` | `BIGINT`, FK `pb_user (id)`                                  | `Mapped[int \| None]`      | |

`pb_user` is the one exception: its `created_by_id` and `updated_by_id` are nullable,
since a person signing up has no creator. `UserOrm` redeclares both.

A foreign key has no `ON DELETE` clause, in the SQL or as `ondelete=` in the Orm, so a
real delete of a referenced row fails loudly instead of quietly removing or unlinking
data. Add a clause only for one of these reasons:

- `CASCADE` on a child that exists only as part of its parent, such as a run's steps.
- `SET NULL` on a log that must outlive what it references.

### Table shape

Every `CREATE TABLE` lists the shared columns in the order of › Shared columns. The
pattern is `migrations/sql/pb_persona/0001_create_pb_persona.up.sql`.

- Table-specific columns go between `identity` and `created_at`.
- A constraint on a single column is written inline and unnamed: `PRIMARY KEY`,
  `UNIQUE`, `REFERENCES pb_user (id)`, `CHECK (...)`. Postgres's generated names match
  the naming convention.
- A constraint spanning several columns goes at table level, named:
  `CONSTRAINT pb_persona_tag_persona_id_tag_id_key UNIQUE (persona_id, tag_id)`.
- If a generated name would pass 63 characters, name the constraint explicitly in both
  the SQL and the Orm class (Postgres truncates; SQLAlchemy shortens differently).
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
  datetimes. A naive datetime raises when it's written.
- Every "now" a query compares with or a write stores comes from the database clock,
  never the app server's `datetime.now(UTC)`. `DatabaseClockUtils`
  (`libs/database/utils/`) builds it as SQL, written into the statement itself:
  `.where(<Orm>.expires_at <= DatabaseClockUtils.build_utc_now_sql())`,
  `.values(<column>=DatabaseClockUtils.build_utc_now_sql())`.
  `build_utc_now_plus_sql(seconds)` is a time that far ahead, such as a lease expiry.
- A service that writes a time takes none from its caller.
- Inside one transaction the database clock is the transaction's start time, so every
  time one transaction writes is the same.
- `datetime.now(UTC)` is only for a time that never reaches the database, such as
  checking a third-party token's expiry. A duration uses `DateTimeUtils`' monotonic
  clock.
- No database triggers. `BaseOrm`'s `onupdate` sets `updated_at` from the database
  clock on every `update()` statement, so only an `UPDATE` written in raw SQL, like a
  backfill, sets it itself.

### Soft delete

- Rows are soft-deleted: set `deleted_at` and `deleted_by_id`. Never `DELETE` in
  application code.
- Sessions from `create_db_session_factory()` (`libs/database/session.py`) add
  `deleted_at IS NULL` to every ORM select, including relationship loads.
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
- Adding members goes in its own revision, apart from any other change, in the same
  commit as the Python change: `ALTER TYPE pb_auth_provider_type ADD VALUE IF NOT EXISTS 'GITHUB'`.
  - `IF NOT EXISTS`, because the `.down.sql` can't remove the value (a comment says
    so), and the stairway test upgrades the revision a second time.
  - Each `ADD VALUE` is its own file, run with `run_non_transactional` (› Transactional
    vs non-transactional), so the value is committed before a later revision uses it.
    Several `ADD VALUE`s to one type may share a revision.
  - Rows that use the new value, such as a seed, go in the next revision.
- A new `PermissionType` member is a schema change: an `ADD VALUE` to
  `pb_permission_type`, then, in the next revision, its `pb_permission` row and a
  `pb_role_permission` grant for each role that holds it.
- Removing a member isn't supported by Postgres. It takes a new type, a column
  migration, and dropping the old type.
- The `.down.sql` for a table using a type drops the type after the table.

## Orm classes

Every table has one module in `libs/database/orm/`, regardless of which domain uses
it. Add each new class to the imports and `__all__` in `libs/database/orm/__init__.py`;
that import is what registers every mapper before configuration.

- Every Orm class extends `BaseOrm`. `BaseOrm` maps annotations to column types:
  `str` → `TEXT`, `datetime` → `UtcDateTime`, `UUID` → `UUID`. Declare `CITEXT`,
  `BIGINT` foreign keys, and enums explicitly.
- Server defaults the SQL declares are mirrored with `server_default` (`false()`,
  `true()`, `text(...)`).
- Indexes and partial unique indexes are declared in `__table_args__` with the exact
  name the SQL uses:
  `Index("pb_user_email_idx", "email", unique=True, postgresql_where=text("deleted_at IS NULL"))`.
- `libs/database/base.py`, `session.py`, `column_types.py`, and `constants.py` are
  setup files. Changing them is a deliberate design change, not part of adding a table.

### References between tables

Use direct symbols, never quoted class names. In a mutual relationship the child
imports the parent directly, and the parent imports the child under `if TYPE_CHECKING:`
to avoid the import cycle; annotations are deferred, so neither side needs quotes.

The pattern is `libs/database/orm/generate_text_run.py` (parent) and
`generate_text_step.py` (child).

- `ForeignKey(<Orm>.id)`, never `ForeignKey("pb_<table>.id")`.
- `__tablename__` and the `back_populates` attribute name are the only permitted loose
  strings, with one exception: `ForeignKey("pb_user.id")` on `BaseOrm`'s audit columns and
  `UserOrm`'s own overrides of them, because `UserOrm` extends `BaseOrm` and can't be
  imported there.
- Add a relationship only in the direction a query uses. A one-way relationship takes
  no `back_populates`: `child: Mapped[ChildOrm] = relationship()`.

## Migrations

Migrations are raw SQL in `backend/migrations/`. They never import application code,
and application code never imports them.

- Alembic is a runner only. **Never** `alembic revision --autogenerate`.
- `migrations/env.py` has no `target_metadata` and reads `DATABASE_URL` from the
  environment, or from `.env`.
- Every schema change produces three things in the same commit: the `.up.sql` and
  `.down.sql` pair, the revision that runs them, and the matching Orm change. Missing
  the Orm change is the most common failure.

### Layout

```
backend/migrations/
├── revisions/
│   └── 20260917_1528_create_user_tables.py
└── sql/
    ├── extensions/                 # CREATE EXTENSION files
    └── pb_user/                    # one folder per table, named exactly as the table
        ├── 0001_create_pb_user.up.sql
        └── 0001_create_pb_user.down.sql
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

The wrapper names SQL files and contains no SQL. The pattern is
`migrations/revisions/20260917_1528_create_user_tables.py`.

- `upgrade()` runs the `.up.sql` files it names; `downgrade()` runs the matching
  `.down.sql` files in reverse order. Nothing is inferred from filenames.
- The chain is append-only. `down_revision` points at the current head
  (`uv run alembic heads`). Never insert a revision between two that have already run;
  a change to an applied migration is a new migration.
- Every migration ships a `.down.sql`. If a change is irreversible, the down file
  carries a comment saying so plus whatever schema-only reversal it can manage. It is
  never omitted.
- Revisions never call `op.execute()`.

### Transactional vs non-transactional

Each revision runs in its own transaction (`transaction_per_migration=True`).
`MigrationRunner` has two methods. Pick deliberately.

- **`run_transactional(path)`** is the default: every statement runs inside the
  revision's transaction, DDL included.
- **`run_non_transactional(path)`** commits what the revision ran so far, runs the
  file's one statement outside a transaction, then opens a fresh one. It raises if the
  file holds more than one statement. Use it only for statements Postgres refuses to
  run in a transaction (`CREATE INDEX CONCURRENTLY`, `DROP INDEX CONCURRENTLY`,
  `REINDEX CONCURRENTLY`, `VACUUM`) and for `ALTER TYPE ... ADD VALUE` (› Enums).
  - A non-transactional statement gets its own file and its own revision (for
    `ADD VALUE`, see Enums). Never bundle a concurrent index with other changes.
  - Name those files for what they are: `0003_add_email_index_concurrently.up.sql`.
  - The `.down.sql` for a concurrent index is also concurrent, and also alone.

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

It compares the database with `BaseOrm.metadata` and fails on any difference in
columns, types, nullability, indexes or constraints. Autogenerate is a detector that
fails the build, never a generator that writes files.
