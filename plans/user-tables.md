# User tables — schema proposal

For step 7 of `plan.md`. This is the design to review before any SQL is written.

## Standards every table follows

- **Singular names with the `pb_` prefix:** `pb_user`, `pb_user_auth_provider`.
- **Two keys per row:**
  - `id` is a `BIGINT` identity column. It's the primary key and what foreign keys
    point at, and it never leaves the backend.
  - `identity` is a UUID v4 that Postgres generates. It's the only ID the API exposes,
    in path parameters (`{blog_post_identity}`), in `IdentityResponseDto`, and in
    response bodies.
- **Timestamps:** `TIMESTAMP` without time zone, always holding UTC.
- **No database triggers.** SQLAlchemy sets `updated_at`. Inserts get their timestamps
  from column defaults. Those are plain `DEFAULT`s, not triggers, so a raw SQL insert
  (like the system user migration) still gets correct timestamps.
- **Soft delete:** `deleted_at` and `deleted_by_id`. A global SQLAlchemy rule adds
  `deleted_at IS NULL` to every ORM query, the way Sequelize's `paranoid` mode does.
  An opt-out for reading soft-deleted rows is designed when something first needs one.
- **Audit columns:** `created_by_id`, `updated_by_id` and `deleted_by_id` reference
  `pb_user(id)`. Services fill them from the `AuthUser` the auth dependency places in
  request scope. The route passes it to the service, which reads `auth_user.id`.
- **Enums:** a Postgres enum type named `pb_<name>_type`, with `UPPER_SNAKE` labels
  that match the Python `StrEnum`.
- **Booleans** start with `is_`.
- **`gen_random_uuid()`** has been built into Postgres since version 13, so UUIDs need
  no extension. `citext` does need one (see Migrations).

### Shared columns

These are defined once, on `BaseOrm` in `libs/database/base.py`. Every Orm class inherits
them.

| Column          | Type        | Null     | Default                           | Notes |
| --------------- | ----------- | -------- | --------------------------------- | ----- |
| `id`            | `BIGINT`    | not null | `GENERATED ALWAYS AS IDENTITY`    | Primary key; used only inside the backend |
| `identity`      | `UUID`      | not null | `gen_random_uuid()`               | Unique; the ID the API exposes |
| `created_at`    | `TIMESTAMP` | not null | `(now() AT TIME ZONE 'utc')`      | |
| `updated_at`    | `TIMESTAMP` | not null | `(now() AT TIME ZONE 'utc')`      | SQLAlchemy `onupdate` sets it on every ORM update |
| `deleted_at`    | `TIMESTAMP` | null     | —                                 | Set means soft-deleted |
| `created_by_id` | `BIGINT`    | see note | —                                 | FK `pb_user(id)` |
| `updated_by_id` | `BIGINT`    | see note | —                                 | FK `pb_user(id)` |
| `deleted_by_id` | `BIGINT`    | null     | —                                 | FK `pb_user(id)` |

- **Nullability of `created_by_id` and `updated_by_id`:** nullable on `pb_user`, since a
  person signing up has no creator. On every other table they're `NOT NULL`.
- **Foreign-key names:** `pb_<table>_created_by_id_fkey` and so on.
- **`ON DELETE`:** the default (`NO ACTION`). Soft delete means real deletes are rare,
  and when one happens it should fail loudly rather than lose history.
- **Python side:** a column type converts timezone-aware UTC datetimes to naive ones on
  the way in, and marks them as UTC on the way out. asyncpg rejects aware datetimes
  for a `TIMESTAMP` column, so the conversion happens in one place.
- **Known trade-off of no triggers:** an `UPDATE` written in raw SQL, like a backfill,
  must set `updated_at` itself.

## `pb_user`

| Column              | Type        | Null     | Default | Notes |
| ------------------- | ----------- | -------- | ------- | ----- |
| *shared columns*    |             |          |         | See above |
| `email`             | `CITEXT`    | not null | —       | Unique among rows that aren't soft-deleted |
| `is_email_verified` | `BOOLEAN`   | not null | `false` | |
| `display_name`      | `TEXT`      | null     | —       | |
| `avatar_url`        | `TEXT`      | null     | —       | |
| `is_active`         | `BOOLEAN`   | not null | `true`  | The normal way to turn off someone's access |
| `is_system_user`    | `BOOLEAN`   | not null | `false` | True only for the system user |
| `last_login_at`     | `TIMESTAMP` | null     | —       | UTC. Set on each sign-in |
| `last_activity_at`  | `TIMESTAMP` | null     | —       | UTC. Set by a middleware on authenticated requests, at most once per interval |

- **Removing access:** set `is_active = false`. Soft-deleting a user is a developer
  action for special cases, not a product feature.
- **Why email is unique only among live rows:** if a user is soft-deleted, the same
  email can sign up again as a fresh account.
- **Upsert gotcha:** an `ON CONFLICT` upsert on `email` must repeat the index's
  condition, `ON CONFLICT (email) WHERE deleted_at IS NULL`, or Postgres won't match
  the index.

Constraints and indexes:

| Name                         | Definition |
| ---------------------------- | ---------- |
| `pb_user_pkey`               | `PRIMARY KEY (id)` |
| `pb_user_identity_key`       | `UNIQUE (identity)` |
| `pb_user_email_idx`          | `UNIQUE (email) WHERE deleted_at IS NULL` |
| `pb_user_is_system_user_idx` | `UNIQUE (is_system_user) WHERE is_system_user` — at most one system user |

## `pb_user_auth_provider`

One row per sign-in provider linked to a user. This lets a user add a second provider
(Auth0, for example) without ending up with two accounts.

| Column              | Type                    | Null     | Default | Notes |
| ------------------- | ----------------------- | -------- | ------- | ----- |
| *shared columns*    |                         |          |         | See above |
| `user_id`           | `BIGINT`                | not null | —       | FK `pb_user(id)` `ON DELETE CASCADE` |
| `provider`          | `pb_auth_provider_type` | not null | —       | `GOOGLE` |
| `provider_subject`  | `TEXT`                  | not null | —       | The provider's `sub` claim |
| `email_at_provider` | `CITEXT`                | null     | —       | Can drift from `pb_user.email` |
| `last_used_at`      | `TIMESTAMP`             | null     | —       | UTC |

Constraints and indexes:

| Name                                         | Definition |
| -------------------------------------------- | ---------- |
| `pb_user_auth_provider_pkey`                 | `PRIMARY KEY (id)` |
| `pb_user_auth_provider_identity_key`         | `UNIQUE (identity)` |
| `pb_user_auth_provider_user_id_fkey`         | `FOREIGN KEY (user_id) REFERENCES pb_user (id) ON DELETE CASCADE` |
| `pb_user_auth_provider_provider_subject_idx` | `UNIQUE (provider, provider_subject) WHERE deleted_at IS NULL` |
| `pb_user_auth_provider_user_id_idx`          | `(user_id)` — Postgres doesn't index foreign keys automatically |

This replaces `google_subject_id` on the user table in `plan.md`.

## Enum types

| Postgres type           | Python `StrEnum`   | Labels |
| ----------------------- | ------------------ | ------ |
| `pb_auth_provider_type` | `AuthProviderType` | `GOOGLE`. More providers are added as labels when they're built |

## Migrations

| Revision | Runs | Notes |
| -------- | ---- | ----- |
| 1 `enable_citext` | `extensions/0001_enable_citext` | Its own revision: other features' tables will use `citext` too, so rolling back the user tables mustn't drop it |
| 2 `create_user_tables` | `pb_user/0001_create_pb_user`, `pb_user_auth_provider/0001_create_pb_user_auth_provider` | The tables in dependency order. Down files run in reverse |
| 3 `insert_system_user` | `pb_user/0002_insert_system_user` | Seed row in its own revision. The down file deletes the row |

- **Extensions:**
  - `CREATE EXTENSION IF NOT EXISTS citext` works the same locally and on Railway, so
    it can be an ordinary migration.
  - `citext` has been a "trusted" extension since Postgres 13, so a database owner can
    install it without superuser rights. Railway's default user is a superuser
    anyway.
  - Extensions aren't ours, so they don't take the `pb_` prefix. Their SQL lives in
    `sql/extensions/`.
- **Tests:** they wipe `pb_test` with `DROP SCHEMA public CASCADE`, which also drops
  `citext`. The next `alembic upgrade head` reinstalls it.

## System user

| Column           | Value |
| ---------------- | ----- |
| `email`          | `system@persona-blog.internal` |
| `display_name`   | `System` |
| `is_system_user` | `true` |
| `is_active`      | `true` |
| everything else  | Defaults, or null |

## Deferred

These return with the features that need them:

- `role` and `tier`
- `persona_limit` and `content_limit` (nullable, null meaning unlimited; enforced by
  counting rows, not a stored counter)

## Naming notes

- **`provider_subject`, not `provider_id`.** Every `_id` column in this schema is a
  `BIGINT` foreign key (`user_id`, `created_by_id`), so `provider_id` would read like a
  reference to a provider table. `provider_subject` matches the OIDC `sub` claim it
  stores.
