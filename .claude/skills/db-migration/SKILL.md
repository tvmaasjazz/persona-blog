---
name: db-migration
description: Make a database schema change in this project. Use whenever a change touches the schema — adding, removing, renaming, or altering a table, column, index, constraint, or enum value; backfilling or transforming existing rows; or any edit to a class under libs/database/orm/. Migrations here are hand-written SQL run through MigrationRunner, never Alembic autogenerate. Usually delegated to the schema-coder agent.
---

# Making a schema change

The conventions are in `.claude/rules/database.md`: naming, table shape, Orm classes,
revisions, transactional vs non-transactional SQL, and the drift check. Read it in full
first. This skill is the procedure only.

## Delegate to `schema-coder`

The `schema-coder` agent writes the SQL, the revision, and the Orm class, then verifies
them against the test database. It doesn't see this conversation, so pass it:

- the table and whether it's new or changing
- every column: name, type, nullability, default
- constraints and indexes, including partial unique indexes on soft-deletable tables
- enum types and their labels, and which lib's `types.py` owns the `StrEnum`
- any backfill, and what should happen to existing rows
- whether a down migration can reverse it

Write the change yourself only when it's too small to be worth the brief. Follow the
same steps.

## Steps

1. **Read** `.claude/rules/database.md`, then the neighbouring SQL folders, the current
   Orm modules, and `libs/database/base.py`.
2. **Find the head** with `uv run alembic heads`. The new revision's `down_revision`
   points at it.
3. **Write the `.up.sql`** in the table's folder, one logical change per file.
4. **Write the `.down.sql`.** Always, even when it's only a comment that the change
   can't be reversed.
5. **Generate the revision** with
   `uv run alembic revision --rev-id <YYYYMMDD_HHMM> -m <slug>`, using the current UTC
   time (`date -u +%Y%m%d_%H%M`), and replace the placeholder paths.
6. **Update the Orm class** in `libs/database/orm/` and the exports in
   `libs/database/orm/__init__.py`.
7. **Verify against the test database** from `backend/`, with docker compose up:

   ```bash
   uv run pytest -m migration
   DATABASE_URL=postgresql+asyncpg://pb:pb@localhost:5437/pb_test uv run python -m scripts.check_schema_drift
   uv run pytest
   ```

   The stairway test rebuilds `pb_test` from empty and leaves it at head, so the drift
   check runs against the new schema. A failure in the full suite after a schema change
   usually means a factory or test needs the new column. That work belongs to
   `be-test-writer`.
8. **Stop.** Never run `alembic upgrade` or `downgrade` against the database in `.env`.
   Report what changed and let Tyler apply it to `pb_local` with
   `uv run alembic upgrade head`.
