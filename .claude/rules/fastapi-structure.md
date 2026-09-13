---
paths:
  - "backend/**/*.py"
---

# Backend structure

Organized by domain, not by technical layer. No global `routers/` or `services/`
folder. `apps/` imports `libs/`, never the reverse.

```
backend/
├── apps/
│   └── api/
│       ├── core/
│       │   ├── config.py      # root AppSettings
│       │   ├── dependencies.py# global deps: db session, current user
│       │   └── dtos.py        # IdentityResponseDto, EmptyResponseDto
│       ├── domains/
│       │   └── users/
│       │       ├── dependencies.py   # factories + Annotated aliases
│       │       ├── router.py
│       │       └── dtos.py
│       ├── lifespan.py        # app-scoped resources on app.state
│       ├── app_factory.py     # create_app()
│       └── main.py            # app = create_app()
├── libs/
│   ├── core/
│   │   └── exceptions.py      # standard exceptions: NotFoundException, ...
│   ├── database/
│   │   ├── base.py            # Base (DeclarativeBase), shared metadata
│   │   ├── session.py         # engine + async_sessionmaker
│   │   └── orm/               # every table, one module per entity
│   │       ├── __init__.py    # imports all modules below
│   │       ├── user.py        # UserOrm
│   │       └── persona.py     # PersonaOrm
│   └── users/
│       ├── services.py        # UserService
│       ├── inputs.py          # CreateUserInput, ...
│       ├── results.py         # CreateUserResult, ...
│       ├── settings.py        # UserSettings (BaseModel)
│       ├── prompts.py         # ...Prompt classes, if the domain uses an LLM
│       ├── exceptions.py      # UserEmailTakenException, if the domain needs its own
│       └── constants.py
├── migrations/                # raw SQL; imports nothing from apps/ or libs/
└── pyproject.toml
```

A second service (worker, scheduler) lands as `apps/<name>/` beside `api/` and
reuses the same `libs/` domains.

## Filenames inside a domain package

The folder supplies the domain, so files inside it are short: `domains/users/router.py`,
never `domains/users/user_router.py`.

Names that escape the package stay fully explicit: `user_router`, `UserService`,
`UserOrm`.

## Layer rules

- **`libs/` has no FastAPI dependency.** `Request`, `Depends`, and `HTTPException`
  anywhere under `libs/` is a bug. Pydantic is fine. Services take what they need
  through `__init__` and must be constructible with no app running.
- **`apps/api/domains/<name>/` owns HTTP concerns only**: payload shapes, status
  codes, dependency wiring. No business rules.
- **A route never returns an `Orm` object.** Map it to a `ResponseDto`.
- **Cross-domain imports go through `libs/`.** `domains/posts/` may import
  `libs.users.services`, never `domains.users.*`.
- **`core/` is for what spans every domain**: db session dependency, current-user
  dependency, root settings, shared response DTOs. Used by only two domains means it
  belongs to a domain.

## DTOs

Never use the word "schema". HTTP payload classes are DTOs, in the domain's
`dtos.py` under `apps/`. The response DTOs every domain shares live in
`apps/api/core/dtos.py`.

### Inbound

A route takes a `Dto` only when a body or a query model is sent.

| Route                                  | Inbound                                                    |
| -------------------------------------- | ---------------------------------------------------------- |
| `POST` create / `PUT` update           | `<Entity>Dto` body, **one class shared by both**: `BlogPostDto` |
| `GET /{id}` / `DELETE /{id}`           | None — the identifier is a plain path parameter            |
| `GET` list                             | `<Entity>FetchAllQueryDto` query model: `BlogPostFetchAllQueryDto` |
| Non-CRUD action (`POST /ai-write`)     | `<Verb><Entity>Dto` body: `GenerateWritingDto`             |

A `FetchAllQueryDto` defines and validates the query string the way a body `Dto`
validates the body, with filters grouped in a nested filter object. Bind it as
`Annotated[BlogPostFetchAllQueryDto, Query()]`. Pagination and filter conventions
are not settled yet — decide them with the first feature that needs them and record
them here.

### Outbound

| Route                          | Returns                                               |
| ------------------------------ | ----------------------------------------------------- |
| `GET`                          | A custom `<Entity>ResponseDto`: `BlogPostResponseDto`  |
| `POST` create                  | `IdentityResponseDto` — `{"identity": "<id>"}`        |
| `PUT` update / `DELETE`        | `EmptyResponseDto` — `{}`                             |
| Non-CRUD action                | A custom `ResponseDto` for what it carries: `WritingResponseDto` |

On a CRUD route, a custom `ResponseDto` appears only on a `GET`. Every route declares
its response DTO as its return annotation.

One `dtos.py` per domain holds both directions. Never split into `requests.py` /
`responses.py`. Split by sub-feature only, once a domain's file gets unwieldy.

A service never accepts or returns a `Dto`.

### Input models

A service method taking a structured payload takes a Pydantic `Input` model from
`libs/<domain>/inputs.py`. Scalar identifiers stay plain parameters —
`get_user(user_id: int)` gets no wrapper. Create and update share the one `Input`
their shared `Dto` maps to: `create_blog_post(blog_post_input: BlogPostInput)` and
`update_blog_post(blog_post_id: int, blog_post_input: BlogPostInput)`.

**Never subclass an `Input` to make a `Dto`.** Declare the `Dto` independently.
Every `Dto` has a `to_input()`; every domain `ResponseDto` has a `from_result()`.
The shared `IdentityResponseDto` and `EmptyResponseDto` are constructed directly.

```python
# apps/api/core/dtos.py
class IdentityResponseDto(BaseModel):
    identity: str


class EmptyResponseDto(BaseModel):
    pass
```

```python
# apps/api/domains/blog_posts/dtos.py
class BlogPostDto(BaseModel):
    title: str
    body: str

    def to_input(self) -> BlogPostInput:
        return BlogPostInput(title=self.title, body=self.body)


class BlogPostResponseDto(BaseModel):
    id: int
    title: str
    body: str

    @classmethod
    def from_result(cls, result: GetBlogPostResult) -> "BlogPostResponseDto":
        return cls(id=result.id, title=result.title, body=result.body)
```

## App-scoped vs request-scoped

`lifespan.py` owns long-lived resources — HTTP pool, SQLAlchemy engine, settings —
created on `app.state` at startup and closed at shutdown. Nothing per-request.

Domain `dependencies.py` reads `Request`, pulls from `app.state`, builds
request-scoped objects, and constructs the service. Export an `Annotated` alias for
each.

```python
# apps/api/core/dependencies.py
async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    db_session_factory = request.app.state.db_session_factory
    async with db_session_factory() as db_session:
        yield db_session


DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]
```

```python
# apps/api/domains/users/dependencies.py
def get_user_service(request: Request, db_session: DbSessionDep) -> UserService:
    http_client: AsyncClient = request.app.state.http_client
    timeout = request.app.state.settings.users.api_timeout_seconds
    return UserService(
        http_client=http_client,
        db_session=db_session,
        api_timeout_seconds=timeout,
    )


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
```

Routers are one line of delegation, type hints only, no `= Depends(...)` defaults:

```python
# apps/api/domains/blog_posts/router.py
blog_post_router = APIRouter(prefix="/blog-posts", tags=["blog-posts"])


@blog_post_router.get("/{blog_post_id}")
async def get_blog_post(
    blog_post_id: int, blog_post_service: BlogPostServiceDep
) -> BlogPostResponseDto:
    get_blog_post_result = await blog_post_service.get_blog_post(blog_post_id)
    return BlogPostResponseDto.from_result(get_blog_post_result)


@blog_post_router.post("/")
async def create_blog_post(
    dto: BlogPostDto, blog_post_service: BlogPostServiceDep
) -> IdentityResponseDto:
    create_blog_post_result = await blog_post_service.create_blog_post(dto.to_input())
    return IdentityResponseDto(identity=str(create_blog_post_result.id))


@blog_post_router.put("/{blog_post_id}")
async def update_blog_post(
    blog_post_id: int, dto: BlogPostDto, blog_post_service: BlogPostServiceDep
) -> EmptyResponseDto:
    await blog_post_service.update_blog_post(blog_post_id, dto.to_input())
    return EmptyResponseDto()


@blog_post_router.delete("/{blog_post_id}")
async def delete_blog_post(
    blog_post_id: int, blog_post_service: BlogPostServiceDep
) -> EmptyResponseDto:
    await blog_post_service.delete_blog_post(blog_post_id)
    return EmptyResponseDto()
```

`app_factory.py` is the only file that knows the full list of domains.

## ORM

Every table lives in `libs/database/orm/`, one module per entity, regardless of which
domain uses it. `libs/database/orm/__init__.py` imports every module in the package —
that import is what guarantees all mappers are registered before configuration.

```python
# libs/database/orm/__init__.py
from libs.database.orm.persona import PersonaOrm
from libs.database.orm.user import UserOrm

__all__ = ["PersonaOrm", "UserOrm"]
```

A service may import any Orm it needs; the domain boundary applies to services, not
tables.

### References between tables

Use direct symbols where import order allows:

```python
# libs/database/orm/persona.py
class PersonaOrm(Base):
    __tablename__ = "personas"

    user_id: Mapped[int] = mapped_column(ForeignKey(UserOrm.id))
    user: Mapped[UserOrm] = relationship(back_populates="personas")
```

- `ForeignKey(UserOrm.id)`, never `ForeignKey("users.id")`.
- `__tablename__` and the `back_populates` attribute name are the only permitted
  loose strings.
- A quoted class name in `relationship()` or `Mapped[...]` is allowed on **one** side
  of a mutual relationship only. Put the forward reference on the parent
  (`UserOrm.personas`) and the concrete import on the child.
- Many-to-many association tables go in `libs/database/orm/associations.py`.

## Database

- Async throughout: `AsyncSession`, `async_sessionmaker`, async driver. Never a sync
  `Session`.
- Engine and `async_sessionmaker` are created once in `lifespan`; db sessions are
  per-request.
- `get_db_session` does **not** commit — a write through it is silently discarded.
  Write routes use a second dependency that owns the transaction:

```python
async def get_db_transaction(request: Request) -> AsyncIterator[AsyncSession]:
    db_session_factory = request.app.state.db_session_factory
    async with db_session_factory() as db_session, db_session.begin():
        yield db_session


DbTransactionDep = Annotated[AsyncSession, Depends(get_db_transaction)]
```

- Never hand-roll a transaction decorator.
- The commit runs in dependency teardown, after the route returns, so a constraint
  violation surfaces as a 500. An endpoint that must turn a duplicate key into a 409
  commits explicitly in the service and uses `DbSessionDep`.
- A service receives a db session; it never creates one, and never commits unless it
  owns the transaction boundary explicitly.
- Async sessions do not lazy-load. Request relationships up front with
  `selectinload()` / `joinedload()`.

### Querying and writing

2.0-style `select()`, never `session.query()`. Statement, execute, extract:

```python
    async def get_user_by_email(self, email: str) -> GetUserByEmailResult | None:
        query = (
            select(UserOrm)
            .where(UserOrm.email == email)
            .options(selectinload(UserOrm.personas))
        )
        query_result = await self._db_session.execute(query)
        user_orm = query_result.scalar_one_or_none()

        if user_orm is None:
            return None
        return GetUserByEmailResult.model_validate(user_orm)
```

`scalar_one_or_none()` for an optional row, `scalar_one()` when absence is a bug,
`scalars().all()` for a list.

Creates use `add()` then `flush()`, never `commit()`. `flush()` populates the primary
key and other server-side defaults:

```python
    async def create_user(self, user_input: CreateUserInput) -> CreateUserResult:
        user_orm = UserOrm(
            email=user_input.email,
            display_name=user_input.display_name,
        )
        self._db_session.add(user_orm)
        await self._db_session.flush()

        return CreateUserResult.model_validate(user_orm)
```

Updates: load the Orm, mutate attributes, `flush()`. Use `update()` / `delete()`
statements only for bulk operations.

## Migrations

Migrations are raw SQL in `backend/migrations/`. They never import application code,
and application code never imports them.

- Alembic is a runner only. **Never** `alembic revision --autogenerate`.
- Each revision is a wrapper that executes `.sql` files through `MigrationRunner`.
- `migrations/env.py` does not import `Base` or any Orm module. No `target_metadata`.

```
backend/migrations/
├── env.py
├── migration_runner.py
├── revisions/
│   ├── 20260912_1423_create_users.py
│   └── 20260914_0902_add_display_name.py
└── sql/
    └── users/                      # one folder per table
        ├── 0001_create_users.up.sql
        ├── 0001_create_users.down.sql
        ├── 0002_add_display_name.up.sql
        └── 0002_add_display_name.down.sql
```

- Revision files are `<YYYYMMDD>_<HHMM>_<slug>.py`, generated via `file_template` in
  `alembic.ini`. Point `version_locations` at `revisions/`.
- SQL files are `<nnnn>_<what_it_does>.<up|down>.sql`, zero-padded to four. The verb
  describes the change: `create_users`, `add_display_name`, `backfill_persona_slug`.
- The numeric prefix orders changes within one table's folder, for human reading
  only. Ordering across tables is Alembic's `down_revision` chain.
- The chain is append-only. Never insert a migration between two that have already
  run; a change to an applied migration is a new migration.
- `upgrade()` runs the `.up.sql` files it names; `downgrade()` runs the matching
  `.down.sql` files in reverse order. Nothing is inferred from filenames.

```python
# revisions/20260912_1423_create_users.py
revision = "20260912_1423"
down_revision = None

RUNNER = MigrationRunner()


def upgrade() -> None:
    RUNNER.run("users/0001_create_users.up.sql")


def downgrade() -> None:
    RUNNER.run("users/0001_create_users.down.sql")
```

- Every migration ships a `.down.sql`. If a change is irreversible, the down file
  carries a comment saying so plus whatever schema-only reversal it can manage — it
  is never omitted.
- `MigrationRunner` supports transactional and non-transactional (autocommit)
  execution. Index builds and other statements that can't run in a transaction use
  the autocommit path.
- Changing a table means writing the SQL file *and* updating the Orm class in the
  same commit.

### Drift check

CI applies all migrations to an empty database and compares the result against the
Orm metadata (`alembic check` with a throwaway `target_metadata`). Autogenerate is a
detector that fails the build, never a generator that writes files.

## Configuration and constants

**No loose literals.** A number, string, URL, timeout, limit, or model name that
carries meaning never appears inline in domain code.

| Kind         | Test                          | Lives in                             |
| ------------ | ----------------------------- | ------------------------------------ |
| **Setting**  | Tunable                       | A settings model, defaults in code   |
| **Constant** | Overriding it would be a bug  | Module-level `UPPER_SNAKE`           |

When in doubt, make it a setting.

### Settings

Settings are defined once, in the lib. There is no app-side duplicate.

- **`libs/<domain>/settings.py` declares the shape and defaults.** A plain Pydantic
  `BaseModel`, `frozen=True`. It knows nothing about TOML, env vars, or file paths.
- **`apps/api/core/config.py` declares where values come from.** The root
  `AppSettings` is the only `BaseSettings` in the codebase.

```python
# libs/humanizer/settings.py
class HumanizerSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    llm_request_timeout_seconds: int = 30
    max_rewrite_passes: int = 3
    model_name: str = "claude-sonnet-4-6"
```

```python
# apps/api/core/config.py
class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        toml_file="config.toml",
        env_nested_delimiter="__",
    )

    humanizer: HumanizerSettings = Field(default_factory=HumanizerSettings)
    users: UserSettings = Field(default_factory=UserSettings)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        toml_settings = TomlConfigSettingsSource(settings_cls)
        return (init_settings, env_settings, dotenv_settings, file_secret_settings, toml_settings)
```

`toml_file` alone loads nothing — the TOML source must be added in
`settings_customise_sources`. Sources earlier in the tuple win, so env vars override
TOML.

Only the root is a `BaseSettings`. Domain settings nested inside it are plain
`BaseModel`s; a nested `BaseSettings` reads the environment independently and ignores
the root's TOML file and `__` delimiter.

```toml
# config.toml — overrides only
[humanizer]
llm_request_timeout_seconds = 60
```

`HUMANIZER__MAX_REWRITE_PASSES=5` overrides the same field from the environment.

- `libs/` never reads a file, never reads `os.environ`, never imports `AppSettings`.
- **A settings instance is always injected, never constructed inside a lib.**
  `AppSettings()` is built once in `lifespan`; that populated instance is handed to
  the service. A lib calling `HumanizerSettings()` itself gets defaults and silently
  ignores every override.
- One or two values go into a service as plain arguments; more than that, pass the
  domain's settings object.
- The TOML file carries only what differs between environments. A setting no
  environment overrides never appears in it.
- Secrets are env-var only, declared on `AppSettings`, never in TOML.

```python
def get_humanizer_service(request: Request) -> HumanizerService:
    app_settings: AppSettings = request.app.state.settings
    llm_client: AsyncClient = request.app.state.llm_client
    return HumanizerService(
        llm_client=llm_client,
        humanizer_settings=app_settings.humanizer,
    )
```

### Constants

`constants.py` is small. It holds values where overriding would break correctness —
values that must match what is already deployed:

```python
# libs/users/constants.py
SESSION_COOKIE_NAME = "sid"
EMAIL_NORMALIZE_PATTERN = re.compile(r"\+[^@]*@")
CACHE_KEY_PREFIX = "users:"
```

Timeouts, limits, retry counts, model names, and feature flags are settings, not
constants. Never use an `Enum` to group unrelated constants.

### Prompts

LLM prompts live in a `Prompt` class per prompt set, in `libs/<domain>/prompts.py`.
Every prompt is a method returning `str`.

```python
# libs/humanizer/prompts.py
class HumanizerPrompt:
    @staticmethod
    def build_system_prompt() -> str:
        return REWRITE_SYSTEM_TEMPLATE.format(rules=AI_TELL_RULES)

    @staticmethod
    def build_user_prompt(draft_text: str, persona_style: str) -> str:
        return REWRITE_USER_TEMPLATE.format(draft=draft_text, style=persona_style)
```

- Method names are `build_<what>_prompt`. Never a bare `prompt()`.
- `@staticmethod` when the prompt is a pure function of its arguments. A prompt set
  needing configuration is a normal class constructed with those values, like a
  service.
- Template text is an `UPPER_SNAKE` constant, in `constants.py` or at the top of
  `prompts.py`. Never inline in the method.
- One `Prompt` class per prompt set, not per domain; several can share `prompts.py`.
- A service never builds a prompt string inline.

## Errors

Code raises plain Python exceptions. Only `app_factory.py` knows status codes.

### Standard exceptions

`libs/core/exceptions.py` holds one exception per error category. They subclass
`Exception` directly and know nothing about HTTP, so any lib can raise them, and so can
`apps/`.

```python
# libs/core/exceptions.py
class NotFoundException(Exception): ...


class ConflictException(Exception): ...


class UnauthorizedException(Exception): ...


class ForbiddenException(Exception): ...


class UnprocessableException(Exception): ...


class RateLimitedException(Exception): ...


class ServiceUnavailableException(Exception): ...
```

Add a category only when a status code isn't covered yet. Never add one for a single
domain.

### Lib exceptions

A lib that needs its own exceptions declares them in `libs/<domain>/exceptions.py`.

- **Name**: `<Domain><What>Exception`, prefixed the way the domain's service is
  (`UserService` → `UserEmailTakenException`, `AiWriteService` →
  `AiWriteInappropriateException`).
- **Parent**: exactly one standard exception, which is where its status code comes
  from. Never subclass `Exception` directly.
- **Domain base**: `<Domain>Exception(Exception)`, only if something catches every
  exception from that domain. A domain base never subclasses a standard exception.
  Specific exceptions list it first:
  `class AiWriteInappropriateException(AiWriteException, UnprocessableException)`.

```python
# libs/users/exceptions.py
class UserEmailTakenException(ConflictException): ...
```

Raise a standard exception directly when its category says everything:
`raise NotFoundException(f"Blog post {blog_post_id} not found")`. Declare a lib
exception when code or a test needs to tell it apart from others in its category.

A service method that a `GET /{id}` route calls raises `NotFoundException` when the row
is missing, so the route stays one line. A lookup that only other services use may
return `None` instead.

### Mapping to status codes

`app_factory.py` maps each standard exception to its status code and registers one
handler per entry. Starlette looks up handlers along the exception's class hierarchy,
so every lib exception gets its parent's status code without an entry of its own.

```python
# apps/api/app_factory.py
STATUS_CODE_BY_EXCEPTION: dict[type[Exception], int] = {
    NotFoundException: 404,
    ConflictException: 409,
    UnauthorizedException: 401,
    ForbiddenException: 403,
    UnprocessableException: 422,
    RateLimitedException: 429,
    ServiceUnavailableException: 503,
}


def build_exception_handler(
    status_code: int,
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def handle_exception(request: Request, exception: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exception)})

    return handle_exception


def create_app() -> FastAPI:
    fastapi_app = FastAPI(lifespan=lifespan)
    for exception_class, status_code in STATUS_CODE_BY_EXCEPTION.items():
        fastapi_app.add_exception_handler(exception_class, build_exception_handler(status_code))
    ...
```

- The error body is `{"detail": "<message>"}`, the same shape as FastAPI's own
  errors. The message goes to the client, so it never carries internals: no SQL, no
  stack traces, no upstream error text.
- Anything not mapped is a bug and returns FastAPI's generic 500.
- Never raise `HTTPException`, in `libs/` or in `apps/`. Dependencies such as the
  auth guard raise a standard exception (`UnauthorizedException`), so every error
  goes through the same map.
- Catch a third-party exception at the lib boundary and raise a standard or lib
  exception from it (`raise LlmUnavailableException(...) from timeout_exception`).
  A third-party exception never reaches `apps/`.
