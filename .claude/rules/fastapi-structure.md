---
paths:
  - "backend/**/*.py"
---

# Backend structure

Organized by domain, not by technical layer. No global `routers/` or `services/`
folder. `apps/` imports `libs/`, never the reverse.

```
backend/
├── apps/api/
│   ├── core/            # spans every domain: AppSettings, DbSessionDep, AuthUserDep,
│   │                    #   require_permissions, shared DTOs, exception map, logging
│   ├── domains/<name>/  # HTTP only: router.py, dtos.py, dependencies.py
│   ├── lifespan.py      # app-scoped resources on app.state, app-lifetime loops
│   └── app_factory.py   # create_app(): the only file that lists every domain
├── libs/
│   ├── core/            # domain-free: exceptions.py, inputs.py, results.py, types.py,
│   │                    #   services/, utils/
│   ├── database/        # BaseOrm, session factory, orm/: see database.md;
│   │                    #   pagination_config.py, results.py, services/ (PaginationService),
│   │                    #   utils/ (DatabaseClockUtils, PaginationQueryUtils)
│   └── <domain>/        # services.py or services/, inputs.py, results.py, settings.py,
│                        #   types.py, constants.py; as needed: exceptions.py, utils/,
│                        #   after_response_tasks.py; LLM work: see langgraph.md
├── migrations/          # raw SQL: see database.md
└── scripts/             # e2e/ walkthroughs, db/ tooling, one-off scripts
```

A second service (worker, scheduler) lands as `apps/<name>/` beside `api/` and reuses
the same `libs/`.

A LangGraph workflow, an LLM prompt or an `OutputFormat` follows `langgraph.md`; read
it before writing one.

## Packages

Every package under `apps/` and `libs/` has an `__init__.py`. It stays empty unless it
does work, like `libs/database/orm/__init__.py` registering every mapper. No namespace
packages.

## Enums

All of a domain's enums live in one module, `types.py`: `libs/<domain>/types.py`, or
`apps/api/domains/<name>/types.py` for a domain with no lib. Enums the whole app uses
live in `apps/api/core/types.py`, or in `libs/core/types.py` when a lib uses them,
since `libs/` can't import `apps/`. Never put an enum in `inputs.py`, `constants.py`, or
`dtos.py`, even when only one of them uses it.

## Logging

Code only calls `structlog.get_logger(__name__)`. Logging is configured once, in
`apps/api/core/logging.py`; `libs/` never configures it.

## Services

A lib with one service keeps it in `services.py`. A lib with more than one has a
`services/` package instead, one module per service class, named after it in
snake_case, with `__init__.py` re-exporting every class so callers import from
`libs.<domain>.services`. Never both.

Split a lib by what it is about, not by how big it gets. A provider gets its own lib
when it has its own HTTP surface, such as routes and a callback (`libs/google_auth/`
beside `libs/auth/`). A provider that only implements another lib's contract stays
inside that lib as one more module in its `services/` package
(`libs/llm/services/openai_llm_service.py`).

Inside a lib, split services by job:

- **A service does one job, and its name says what.** Its one-sentence docstring is
  the test: if describing it needs an "and" joining unrelated jobs, the new work gets
  its own service.
- **Machinery around a flow gets its own service.** Work that runs alongside a flow
  rather than being the flow, such as a lease, a heartbeat, or a retry or polling loop,
  is a `<Domain><Thing>Service` of its own, even when only one service calls it. The
  pattern is `libs/generate_text/services/generate_text_run_lease_service.py`.
- **A loop that runs for the app's lifetime lives with what it acts on.** A pickup
  loop or a queue listener is a method on the lib service it acts on. The pattern is
  `pick_up_expired_runs()` in
  `libs/generate_text/services/generate_text_run_pickup_service.py`. Wiring: App-scoped
  vs request-scoped. `apps/api/core/` holds only loops that belong to no domain.
- **A method that acts on any user's rows lives in `libs/admin/`** as
  `Admin<Entity>Service`, so a non-admin route can't call it by mistake; other services
  check ownership (the caller's own rows, or public ones). Every class in `libs/admin/`
  and `apps/api/domains/admin/` takes the `Admin` prefix, so its inputs, results and
  DTOs never share a name with the owning domain's. Admin routes share one router under
  `/admin`. An admin service reads directly, but writes through the owning domain's
  service when that service already makes the same write, so the domain's rules stay
  in one place; a write only an admin makes is the admin service's own.

### Validation guards

A check that needs only a field's own value, however involved, is a DTO
`field_validator` that calls a pure `<Domain>ValidationUtils` in the lib and raises
`ValueError` with the problems it returns (reference: `BlogPostValidationUtils`). The
name says what it validates, never `Dto`: a service may run the same check.

A check that needs a database read or compares more than one field is a validation
guard: a dependency in the domain's `dependencies.py`, named `validate_<what>` and
attached with `dependencies=[Depends(...)]` after the route's permission (DTOs › The
acting user). It calls a `validate_<condition>()` method on the lib's
`<Domain>ValidationService`, which returns nothing and raises a lib exception when the
payload is invalid. Reference: `apps/api/domains/personas/dependencies.py`.

The validation service holds only the methods a guard calls. Business services never
validate payloads this way, and access control, such as whether the caller may change
a row, stays in the business service that loads the row.

### Dependencies that open their own session

On a route that waits on an LLM or starts a background job, a dependency that reads
the database — a validation guard, or a row the route needs — opens its own short
session from `request.app.state.db_session_factory`, closed before the route runs. It
builds the service it calls on that session, so it takes no `...ServiceDep`, and
returns a row as a `Result` the route passes to its service. A request session held
open there would sit idle inside an open transaction, and in tests clash with the
job's session. The pattern is `get_generate_text_persona` and
`validate_active_run_limit` in `apps/api/domains/generate_text/dependencies.py`.

### Utils

A `Utils` class lives in `libs/<domain>/utils/`, one module per class, with
`__init__.py` re-exporting each one (`python-naming.md` › Class suffixes). A service
keeps orchestration; the shaping of what it passes and returns moves out. Utils with
no domain live in `libs/core/utils/`, and a `Result` one of them returns in
`libs/core/results.py`.

Retrying splits the same way: whether an error is retryable and how long to wait are
pure calculations on the provider's `Utils`; the loop that waits and calls again stays
in the service.

### After-response tasks and background jobs

Two kinds of work happen outside a route's own response, named apart so they're never
confused:

- **After-response task:** short work run once the response is sent, such as
  recording a user's activity. A function in `libs/<domain>/after_response_tasks.py`,
  scheduled with FastAPI's `BackgroundTasks` through a parameter named
  `after_response_tasks`, from the dependency or route that knows it's needed. It's a
  function rather than a service because it's scheduled per request with the values it
  acts on.
- **Background job:** work that runs for minutes and outlives the request, such as a
  graph run. A private method on its domain service, started with
  `BackgroundJobService.start()` (`libs/core/services/`) and drained at shutdown. The
  machinery around a job, such as its lease, is a service of its own (Services).

Neither uses the request's session, which has committed and closed by then. A task
that writes the database takes the session factory and opens its own session and
transaction, or hands the factory to a service that opens its own sessions. A task
that only touches Redis takes the Redis client and builds the service it needs. Every
service a background job calls takes the session factory and opens a short session per
write. A task that acts on several rows logs a failure on one and carries on with the
rest.

When one of those short transactions must also hold another service's writes, that
service is built inside the transaction on its `db_session` and never commits.
Everywhere else a service's collaborators arrive through `__init__`.

Everything else a task or job needs — the Redis client, the domain's settings, the
values it acts on — is passed in, so `libs/` never imports `AppSettings`.

### Records that must survive a rollback

A service that writes a record which must survive the caller's rollback, such as a log
of calls to a paid API, takes the session factory and commits each write in its own
short transaction. The pattern is `libs/llm/services/llm_call_service.py`. Never hold one of those sessions open across a slow call: open,
write, commit, close.

## Layer rules

- **`libs/` has no FastAPI dependency.** `Request` or `Depends` anywhere under `libs/`
  is a bug, and so is `HTTPException` anywhere (Errors). Pydantic is fine. Services take what they need
  through `__init__` and must be constructible with no app running.
- **`apps/api/domains/<name>/` owns HTTP concerns only**: payload shapes, status
  codes, dependency wiring. No business rules.
- **A route never returns an `Orm` object.** Map it to a `ResponseDto`.
- **A domain owns one `router.py`.** A second kind of the same thing, such as another
  sign-in provider, becomes its own domain and its own lib rather than a second router
  file.
- **Cross-domain imports go through `libs/`.** `domains/posts/` may import
  `libs.users.services`, never `domains.users.*`. The one exception is a domain's
  `dependencies.py`, which may import another domain's `...ServiceDep` rather than
  building the same service twice. When a route needs two domains' services to do one
  thing, compose them in a lib service that takes both through `__init__` — libs may
  depend on libs — so the route keeps one dependency.
- **A lib never imports a lib that imports it back.** Inside one lib the same cycle
  appears through the package `__init__`, such as a registry whose builders need the
  lib's services while a service needs the registry. The service imports the other
  side under `if TYPE_CHECKING:` and receives the instance through `__init__`.
- **`core/` is for what spans every domain**: db session dependency, current-user
  dependency, root settings, shared response DTOs. Used by only two domains means it
  belongs to a domain.
- **`scripts/` may import `libs/`; nothing imports `scripts/`.** Python scripts run as
  modules from `backend/`.

## DTOs

HTTP payload classes are DTOs, in the domain's `dtos.py` under `apps/`. The DTOs and
field types every domain shares, such as `IdentityResponseDto`, `BasePageQueryDto`,
`BasePageResponseDto` and `UsdDecimal`, live in `apps/api/core/dtos.py`. One `dtos.py` per domain holds both directions; never split
into `requests.py` / `responses.py`. Split by sub-feature only, once a domain's file
gets unwieldy.

A service never accepts or returns a `Dto`. **Never subclass an `Input` to make a
`Dto`**; declare the `Dto` independently. Every `Dto` has a `to_input()`; every domain
`ResponseDto` has a `from_result()`. The shared `IdentityResponseDto` and
`EmptyResponseDto` are constructed directly.

```python
class BlogPostDto(BaseModel):
    title: str
    body: str

    def to_input(self) -> UpdateBlogPostInput:
        return UpdateBlogPostInput(title=self.title, body=self.body)


class BlogPostResponseDto(BaseModel):
    identity: UUID
    title: str

    @classmethod
    def from_result(cls, find_blog_post_result: FindBlogPostResult) -> "BlogPostResponseDto":
        return cls(identity=find_blog_post_result.identity, title=find_blog_post_result.title)
```

### Inbound

A route takes a `Dto` only when a body or a query model is sent.

| Route                                  | Inbound                                                    |
| -------------------------------------- | ---------------------------------------------------------- |
| `POST` create / `PUT` update           | `<Entity>Dto` body, **one class shared by both**: `PersonaDto`. Create gets its own `Create<Entity>Dto` only when it carries fields an update must never change (see Input models) |
| `GET /{identity}` / `DELETE /{identity}` | None — the entity's `identity` is a plain `UUID` path parameter |
| `GET` page                             | `<Entity>PageQueryDto` query model: `PublicBlogPostPageQueryDto` (› Paged routes) |
| `GET` list, everything in one response | `<Entity>FetchAllQueryDto` query model: `BlogPostFetchAllQueryDto` |
| Non-CRUD action (`POST /generate-text`) | `<Verb><Entity>Dto` body: `GenerateTextDto`                |

A query model validates the query string the way a body `Dto` validates the body.
Bind it as `Annotated[PublicBlogPostPageQueryDto, Query()]`. A route over a collection
that can grow is a paged route (› Paged routes); a `FetchAllQueryDto` is only for one
that returns everything at once.

A limit on a request field, such as required, length or format, is part of the API
contract, so it is declared on the `Dto` field, where it reaches the OpenAPI schema
the frontend is generated from. Declare it as an
`Annotated[str, StringConstraints(...)]` alias at the top of `dtos.py`, named for what
it holds, and strip whitespace on required text so `"  "` fails `min_length=1`. The
pattern is `PersonaNameStr` in `apps/api/domains/personas/dtos.py`.

A check that needs the database, or more than one field, is a validation guard
(Services › Validation guards).

### Outbound

| Route                          | Returns                                               |
| ------------------------------ | ----------------------------------------------------- |
| `GET /{identity}`              | A custom `<Entity>ResponseDto`: `BlogPostResponseDto`  |
| `GET` page                     | `<Entity>PageResponseDto` extending `BasePageResponseDto`: `{"blog_posts": [...], "pagination": {...}}` |
| `GET` list                     | `<Entity>ListResponseDto`, rows under a plural field: `{"blog_posts": [...]}` |
| `POST` create                  | `IdentityResponseDto` — `{"identity": "<uuid>"}`, status 201 |
| `PUT` update / `DELETE`        | `EmptyResponseDto` — `{}`                             |
| Non-CRUD action                | A custom `ResponseDto` for what it carries: `GeneratedTextResponseDto` |

On a CRUD route, a custom `ResponseDto` appears only on a `GET`. Every route declares
its response DTO as its return annotation.

A USD amount in a response DTO is a `UsdDecimal`, never a bare `Decimal`, which would
write a rounded zero as `"0E-10"`.

Rows are never a bare array. The service returns a `Result` and the route a
`ResponseDto`, each holding the rows under a plural field. A page or list of the
signed-in user's own rows says so: `find_user_blog_post_list()` returns
`FindUserBlogPostListResult`, and the route is `find_user_blog_post_list` too.

A route on the collection itself uses the path `""`, never `"/"`, which makes a call to
`/blog-posts` answer with a redirect.

A redirecting route returns an annotated `RedirectResponse` and sets any cookie on it.
A route that returns a DTO but sets or clears a cookie takes `response: Response`,
calls `set_cookie()` or `delete_cookie()` on it, and still returns its `ResponseDto`.

### Paged routes

A paged route returns one page of a collection, and every one pages, sorts, filters and
searches the same way. Its names say page where an unpaged route says list:
`find_<…>_page`, `Find<…>PageInput`, `Find<…>PageResult`, `<Entity>PageQueryDto` and
`<Entity>PageResponseDto`. The shared pieces that do the paging are `Pagination…`. The
pattern is `find_public_blog_post_page`, from `apps/api/domains/blog_posts/router.py`
down to `PUBLIC_BLOG_POST_PAGINATION_CONFIG`.

- The `<Entity>PageQueryDto` extends `BasePageQueryDto` and adds `sort_by`, typed as
  the route's `<Entity>SortType` with its default, plus its filters. Its `to_input()`
  builds the route's `Find<…>PageInput`, which extends `BasePageInput`, carrying
  `to_pagination_input()` as its `pagination_input`.
- Filters are flat, typed fields, one value each, never a nested object. A missing
  field filters nothing.

  | Kind        | Name                             | Operator     |
  | ----------- | -------------------------------- | ------------ |
  | Equals      | `<field>`                        | `EQUALS`     |
  | Any of      | plural `<fields>`, a `list[...]` | `IN`         |
  | Range       | `<field>_from`, `<field>_to`     | `GTE`, `LT`  |
  | Has a value | `has_<field>`                    | `HAS_VALUE`  |

- A datetime filter is an `AwareDatetime`, so a time without a zone is a 422. An any-of
  `list[...]` filter takes a `max_length`.
- Filters only narrow. Who may see what stays in the service's all-records query.
- A `PaginationConfig` in the lib's `constants.py` names the search columns, each sort
  value's column, each filter field's `PaginationFilterConfig` (column and operator),
  and the tiebreak column. Add each new one and its `Input` to the config guard test
  (`pytest-testing.md` › What to write for each source file).
- The service builds its all-records query (the joins and who may see what) and makes
  one call, `PaginationService.find_page`, passing the `PaginationConfig`, its `Input`,
  and its loader options as `load_options`. `find_page` counts with `count(*) OVER ()`
  on the page query, and runs a separate count only for an empty page past the first.
- The `<Entity>PageResponseDto` extends `BasePageResponseDto`, and its `Result` carries
  `pagination: PaginationResult`, mapped with `PaginationResponseDto.from_result()`.

### Identifiers

Every row has two keys. `id` is the `BIGINT` primary key and never leaves the backend:
not in a DTO, a path, or a query string. `identity` is the UUID the API exposes, typed
`UUID` everywhere it appears, so a malformed one is a 422 before a service sees it.
Routes and services look rows up by `identity`; foreign keys and joins use `id`.

### Input models

A service method taking a structured payload takes a Pydantic `Input` model from
`libs/<domain>/inputs.py`. Scalar identifiers stay plain parameters —
`find_user(user_identity: UUID)` gets no wrapper. Create and update share the one
`Input` their shared `Dto` maps to:
`create_persona(persona_input: PersonaInput, auth_user: AuthUser)` and
`update_persona(persona_identity: UUID, persona_input: PersonaInput, auth_user: AuthUser)`.

When create carries fields an update must never change, such as an owning parent row,
create gets its own `Create<Entity>Dto` and `Create<Entity>Input`, and update keeps
`<Entity>Dto` with an `Update<Entity>Input`:
`create_blog_post(create_blog_post_input: CreateBlogPostInput, auth_user: AuthUser)` and
`update_blog_post(blog_post_identity: UUID, update_blog_post_input: UpdateBlogPostInput, auth_user: AuthUser)`.

### The acting user

`AuthUserDep` in `core/dependencies.py` resolves the session to an `AuthUser` carrying
the signed-in user's `id`, `identity`, `role` and `permissions`. A route that needs
the acting user takes `AuthUserDep` and passes the `AuthUser` to the service. Any
service method that writes takes it as its last parameter and fills the audit columns
from `auth_user.id`. A write with no signed-in user, such as one made during sign-in,
takes the author's user id instead (`granted_by_id`). Services never read the current
user from anywhere else.

A route lists the permission it needs first in its `dependencies`, before any
validation guard, so a caller without it is refused before anything is read. The
pattern is `create_persona` in `apps/api/domains/personas/router.py`.

`require_permissions(...)` raises `ForbiddenException` unless the user holds every
permission named. Code checks permissions, never roles. Every route names a
permission, reads included, unless it's open by design; an open route goes on
`OPEN_ROUTES` in `tests/api/test_app_factory.py`, which fails on a route that does
neither. A read permission sits in front of the service's own access check, such as
ownership or a public flag, and doesn't replace it.

A read anyone may make, signed in or not, is its own route at
`/{<entity>_identity}/public` beside the owner's `GET` in the same router: no
permission, on `OPEN_ROUTES`, taking `OptionalAuthUserDep`, which is `None` without a
session cookie and still a 401 for an expired one. Its service method takes
`auth_user: AuthUser | None`, and its response holds only the fields a reader sees,
plus `is_owner`. The owner's `GET` returns every field and a 404 to anyone else. The
pattern is `find_public_persona` in `apps/api/domains/personas/router.py`.

## App-scoped vs request-scoped

`lifespan.py` owns long-lived resources — HTTP pool, SQLAlchemy engine, settings —
created on `app.state` at startup and closed at shutdown. Nothing per-request. It also
starts the app-lifetime loops (Services), each from a service built by a
`build_<service>(app_state)` in its domain's `dependencies.py`, which takes `app.state`
rather than a `Request`. A loop starts after the resources it uses, and at shutdown it
is cancelled before background jobs drain, so a stopping process claims no new work.
Loops don't start in the test environment; a test calls the method one pass runs.
`lifespan.py` imports only the `build_<service>` functions of domains that run a loop.

A domain's `dependencies.py` builds request-scoped objects and the service from
`app.state` and other dependencies. Each factory is followed immediately by its
`Annotated` alias, and a factory that takes another alias comes after the one it uses.
The pattern is `apps/api/domains/users/dependencies.py`.

Routers are one line of delegation, type hints only, no `= Depends(...)` defaults. A
route's permission and validation guards go in the decorator's `dependencies` (DTOs ›
The acting user). Routes are ordered `GET` page or list, `GET` one, `POST`, `PUT`, `DELETE`.
Reference: `apps/api/domains/blog_posts/router.py`.

## Database

Tables, Orm classes, and migrations follow `database.md`. This section covers how
application code uses the database.

- Async throughout: `AsyncSession`, never a sync `Session`.
- Sessions come only from `create_db_session_factory(db_engine)`, never a hand-built
  `async_sessionmaker`: the factory carries the session options and the soft-delete
  rule.
- A request has one session, `DbSessionDep`, used by every route, reads included. It
  commits after the route returns and rolls back if the route raises. Never hand-roll
  a transaction decorator.
- A session is opened anywhere else only by a dependency that opens its own session, an
  after-response task or background job and the services they hand the session factory
  to, and a record that must survive a rollback (all under Services). Otherwise a
  service receives its session and never commits it.
- The commit runs in dependency teardown, so a constraint violation surfaces as a 500,
  and that's intended: a service never catches `IntegrityError` to translate it. A
  clash the client needs to hear about, such as a duplicate name, is caught before the
  write by a validation guard; the constraint stays as the backstop against races.
- A service may import any Orm it needs; the domain boundary applies to services, not
  tables.
- A time written comes from `DatabaseClockUtils`, never `datetime.now()` or the caller
  (`database.md` › Timestamps).
- Deleting a row is an `update()` that sets `deleted_at` and `deleted_by_id`, never
  `DELETE`. ORM selects already exclude soft-deleted rows (`database.md` › Soft delete).
- Async sessions do not lazy-load. Load relationships up front with `selectinload()` /
  `joinedload()`.

### Querying and writing

2.0-style `select()`, never `session.query()`. One row: `scalar_one_or_none()`, then
`NotFoundException` on `None`. A list: `scalars().all()`, which is empty rather than an
error. Reference: `libs/personas/services/persona_service.py`.

A record becomes a `Result` through `<Result>.model_validate(<entity>_record,
from_attributes=True)`, which copies only the fields the `Result` declares, including
nested `Result`s. The flag goes on the call; a `Result` never sets `model_config`. A
`Result` that adds a value the record doesn't hold, such as a flag computed from a
setting, is built with its constructor, and the added field has no default so a caller
can't forget it. A `Result` that adds a computed field to an existing detail `Result`
wraps it (`blog_post: BlogPostDetailResult`) instead of copying or subclassing its
fields. A `Result` spanning related rows loads them up front: `contains_eager`
when the query already joins them, `selectinload` otherwise. A labelled multi-column
`select()` read through `.mappings()` is only for flat projections and aggregates.

Writes are one statement each: `insert()` to create and `update()` to change, never
`add()` and `flush()`, and never setting attributes on a loaded record. A statement
lists every column it sets in `.values(...)`, never `**input.model_dump()`, so a
renamed field can't write to the wrong column. A create returns what its caller needs
with `.returning(<Orm>.identity)`. A nullable `JSONB` column is cleared with
`null()`, never `None`, which stores JSON `null` and passes `IS NOT NULL`. Tests,
factories and e2e seed scripts still use the Orm with `add()`, attributes and
`flush()` (`pytest-testing.md` › Test data).

An update that needs an access check reads the row first, in its own query that raises
`NotFoundException` or `ForbiddenException`, then updates it by `id`. One with no
access check skips the read: its `WHERE` is the lookup, and a row count of 0 raises
`NotFoundException`. The soft-delete rule only filters selects, so on a table whose
rows are soft-deleted that `WHERE` adds `<Orm>.deleted_at.is_(None)`.

**A write that moves a row to a new status, or claims it, names the statuses it moves
from in its `WHERE`**, so a late write from a job that's being stopped can't undo a
newer one. A row count of 0 then means the row moved on, which is not an error; when
an unknown row must still raise, a read of its id tells the two apart. When writes
from different sessions touch a parent row and its children, each locks the parent
first with `with_for_update()`, so two transactions never wait on each other's rows.

## Configuration and constants

**No loose literals.** A number, string, URL, timeout, limit, or model name that
carries meaning never appears inline in domain code.

| Kind         | Test                          | Lives in                             |
| ------------ | ----------------------------- | ------------------------------------ |
| **Setting**  | Tunable                       | A settings model, defaults in code   |
| **Constant** | Overriding it would be a bug  | Module-level `UPPER_SNAKE`           |
| **Request field limit** | Part of the API contract | An `Annotated` alias in the domain's `dtos.py` (DTOs › Inbound) |

When in doubt, make it a setting, unless it is a request field's limit.

### Settings

Settings are defined once, in the lib. There is no app-side duplicate.

```python
# libs/humanizer/settings.py
class HumanizerSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    llm_request_timeout_seconds: int = 30
    max_rewrite_passes: int = 3
```

- **`libs/<domain>/settings.py` declares the shape and defaults**, as a frozen
  `BaseModel` that knows nothing about TOML, env vars, or file paths. It is registered
  on `AppSettings` in `apps/api/core/config.py` as
  `<domain>: <Domain>Settings = Field(default_factory=<Domain>Settings)`.
- **The root `AppSettings` is the only `BaseSettings`.** A nested `BaseSettings` reads
  the environment independently and ignores the root's TOML file and `__` delimiter.
- Env vars override `config.toml`: `HUMANIZER__MAX_REWRITE_PASSES=5`. The TOML file
  carries only what differs between environments; a setting no environment overrides
  never appears in it.
- Secrets are env-var only, declared on `AppSettings`, never in TOML.
- **Whether an integration is on is a setting of its own,** overridable like any other
  (`config.toml` or an env var: `<DOMAIN>__IS_ENABLED=true`). It's `is_enabled` when
  the integration is on or off, or a `<Thing>Type` enum when it chooses between backends
  (`<DOMAIN>__<FIELD>=<MEMBER>`). Never infer it from whether the integration's key is
  set. On with what it needs missing, such as its key or endpoint, refuses to start.
- `libs/` never reads a file, never reads `os.environ`, never imports `AppSettings`.
- **A settings instance is always injected, never constructed inside a lib.** A lib
  calling `HumanizerSettings()` itself gets defaults and silently ignores every
  override.
- One or two values go into a service as plain arguments; more than that, pass the
  domain's settings object.

### Constants

`constants.py` is small. It holds values where overriding would break correctness,
values that must match what is already deployed, such as a cookie name, a cache key
prefix or a normalizing regex.

Timeouts, operational limits (rate limits, batch sizes, retry counts), model names,
and feature flags are settings, not constants. A request field's limit is neither; it
belongs on the DTO (DTOs › Inbound). Never use an `Enum` to group unrelated constants.

A lookup map between a lib's own types is a constant named `<VALUE>_BY_<KEY>`. When a
subclass has to match before its parent, it's a tuple of pairs in that order rather
than a dict. The `Utils` class that reads it does the matching.

## Errors

Code raises plain Python exceptions. Only `apps/api/core/exception_handlers.py` knows
status codes.

### Standard exceptions

`libs/core/exceptions.py` holds one exception per error category. Each subclasses
`Exception` directly and knows nothing about HTTP, so any lib can raise it, and so can
`apps/`. `apps/api/core/exception_handlers.py` maps each to its status code:
`NotFoundException` 404, `ConflictException` 409, `UnauthorizedException` 401,
`PaymentRequiredException` 402, `ForbiddenException` 403, `UnprocessableException`
422, `RateLimitedException` 429, `ServiceUnavailableException` 503. A lib exception
gets its parent's status code with no entry of its own.

Add a category only when a status code isn't covered yet. Never add one for a single
domain.

### Lib exceptions

A lib that needs its own exceptions declares them in `libs/<domain>/exceptions.py`.

- **Name**: `<Domain><What>Exception`, prefixed the way the domain's service is
  (`UserService` → `UserEmailTakenException`).
- **Parent**: exactly one standard exception, which is where its status code comes
  from. Never subclass `Exception` directly.
- **Domain base**: `<Domain>Exception(Exception)`, only if something catches every
  exception from that domain. A domain base never subclasses a standard exception.
  Specific exceptions list it first:
  `class GenerateTextInappropriateException(GenerateTextException, UnprocessableException)`.

Raise a standard exception directly when its category says everything:
`raise NotFoundException(f"Blog post {blog_post_identity} not found")`. Declare a lib
exception when code or a test needs to tell it apart from others in its category.

A `find_` method for a single row raises `NotFoundException` when the row is missing,
never returns `None`, so the route that calls it stays one line. That holds for
lookups only other services use too: a caller that expects absence catches the
exception.

### Rules

- The error body is `{"detail": "<message>"}`. The message goes to the client, so it
  never carries internals: no SQL, no stack traces, no upstream error text.
- Anything not mapped is a bug and returns FastAPI's generic 500.
- Never raise `HTTPException`, in `libs/` or in `apps/`. Dependencies such as the auth
  guard raise a standard exception (`UnauthorizedException`), so every error goes
  through the same map.
- Catch a third-party exception at the lib boundary and raise a standard or lib
  exception from it (`raise LlmUnavailableException(...) from timeout_exception`). A
  third-party exception never reaches `apps/`.
- **A route the browser navigates to answers a failure with a redirect**, since JSON
  would leave the user on the API's URL. The lib owns the map from exception to error
  code, and the tuple the route catches, in its `constants.py`; its `Utils` does the
  matching and builds the frontend URL from a `frontend_url` passed in. The route only
  catches and redirects. The values of the error enum are the query values the
  frontend reads. An exception not in the map still reaches the standard handlers.
  Reference: the Google sign-in callback and `GoogleAuthUtils`.
