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
│       │   ├── dtos.py        # IdentityResponseDto, EmptyResponseDto
│       │   ├── exception_handlers.py # standard exception → status code map
│       │   ├── logging.py     # configure_logging(), called once from lifespan
│       │   └── types.py       # app-wide enums: EnvironmentType
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
│   ├── database/              # tables, Orm classes: see database.md
│   │   ├── base.py            # BaseOrm: shared columns every table inherits
│   │   ├── column_types.py    # UtcDateTime
│   │   ├── constants.py       # naming convention, UTC_NOW_SQL
│   │   ├── session.py         # create_db_session_factory(), soft-delete rule
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
│       ├── types.py           # every StrEnum the domain owns
│       └── constants.py
├── migrations/                # raw SQL; see database.md
├── scripts/                   # developer and CI scripts: check_schema_drift.py
├── alembic.ini
└── pyproject.toml
```

A second service (worker, scheduler) lands as `apps/<name>/` beside `api/` and
reuses the same `libs/` domains.

## Packages

Every package under `apps/` and `libs/` has an `__init__.py`. It stays empty unless it
does work, like `libs/database/orm/__init__.py` registering every mapper. The tree
above lists only the ones that do work. No namespace packages. `tests/` is the
exception and has no `__init__.py` at all (see `pytest-testing.md`).

## Enums

All of a domain's enums live in one module, `types.py`: `libs/generate_text/types.py`
holds `TextType`. A domain with no lib, like `health`, keeps its enums in
`apps/api/domains/<name>/types.py`. Enums the whole app uses, like
`EnvironmentType`, live in `apps/api/core/types.py`. Never put an enum in `inputs.py`,
`constants.py`, or `dtos.py`, even when only one of them uses it.

## Logging

`apps/api/core/logging.py` configures structlog once, through
`configure_logging(app_settings)`, called at the start of `lifespan` before anything
logs. Everything else only calls `structlog.get_logger(__name__)`. `libs/` never
configures logging.

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
  `libs.users.services`, never `domains.users.*`. When a route needs two domains'
  services to do one thing, compose them in a lib service that takes both through
  `__init__` — libs may depend on libs — so the route keeps one dependency.
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
| `GET /{identity}` / `DELETE /{identity}` | None — the entity's `identity` is a plain `UUID` path parameter |
| `GET` list                             | `<Entity>FetchAllQueryDto` query model: `BlogPostFetchAllQueryDto` |
| Non-CRUD action (`POST /generate-text`) | `<Verb><Entity>Dto` body: `GenerateTextDto`                |

A `FetchAllQueryDto` defines and validates the query string the way a body `Dto`
validates the body, with filters grouped in a nested filter object. Bind it as
`Annotated[BlogPostFetchAllQueryDto, Query()]`. Pagination and filter conventions
are not settled yet — decide them with the first feature that needs them and record
them here.

### Outbound

| Route                          | Returns                                               |
| ------------------------------ | ----------------------------------------------------- |
| `GET`                          | A custom `<Entity>ResponseDto`: `BlogPostResponseDto`  |
| `POST` create                  | `IdentityResponseDto` — `{"identity": "<uuid>"}`      |
| `PUT` update / `DELETE`        | `EmptyResponseDto` — `{}`                             |
| Non-CRUD action                | A custom `ResponseDto` for what it carries: `GeneratedTextResponseDto` |

On a CRUD route, a custom `ResponseDto` appears only on a `GET`. Every route declares
its response DTO as its return annotation.

Two exceptions involve a real `Response`. A route that redirects returns
`RedirectResponse`, annotated as such, and sets any cookie on that response. A route
that returns a DTO but must set or clear a cookie takes a plain `response: Response`
parameter, calls `response.set_cookie()` or `response.delete_cookie()` on it, and still
returns its declared `ResponseDto`.

One `dtos.py` per domain holds both directions. Never split into `requests.py` /
`responses.py`. Split by sub-feature only, once a domain's file gets unwieldy.

A service never accepts or returns a `Dto`.

### Identifiers

Every row has two keys (`database.md` › Shared columns). `id` is the `BIGINT` primary key and never
leaves the backend: not in a DTO, a path, or a query string. `identity` is the UUID
the API exposes, typed `UUID` everywhere it appears, so FastAPI rejects a malformed
one with a 422 before a service sees it. Routes and services look rows up by
`identity`; foreign keys and joins use `id`.

### Input models

A service method taking a structured payload takes a Pydantic `Input` model from
`libs/<domain>/inputs.py`. Scalar identifiers stay plain parameters —
`find_user(user_identity: UUID)` gets no wrapper. Create and update share the one
`Input` their shared `Dto` maps to:
`create_blog_post(blog_post_input: BlogPostInput, auth_user: AuthUser)` and
`update_blog_post(blog_post_identity: UUID, blog_post_input: BlogPostInput, auth_user: AuthUser)`.

### The acting user

The auth guard, `AuthUserDep` in `core/dependencies.py`, resolves the session to an
`AuthUser` in request scope, carrying the signed-in user's `id` and `identity`. A
route that needs the acting user takes `AuthUserDep` and passes the `AuthUser` to the
service. Any service method that writes takes it as its last parameter and fills the
audit columns from `auth_user.id`. Services never read the current user from
anywhere else.

**Never subclass an `Input` to make a `Dto`.** Declare the `Dto` independently.
Every `Dto` has a `to_input()`; every domain `ResponseDto` has a `from_result()`.
The shared `IdentityResponseDto` and `EmptyResponseDto` are constructed directly.

```python
# apps/api/core/dtos.py
class IdentityResponseDto(BaseModel):
    identity: UUID


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
    identity: UUID
    title: str
    body: str

    @classmethod
    def from_result(cls, result: FindBlogPostResult) -> "BlogPostResponseDto":
        return cls(identity=result.identity, title=result.title, body=result.body)
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


@blog_post_router.get("/{blog_post_identity}")
async def find_blog_post(
    blog_post_identity: UUID, blog_post_service: BlogPostServiceDep
) -> BlogPostResponseDto:
    find_blog_post_result = await blog_post_service.find_blog_post(blog_post_identity)
    return BlogPostResponseDto.from_result(find_blog_post_result)


@blog_post_router.post("/")
async def create_blog_post(
    dto: BlogPostDto, auth_user: AuthUserDep, blog_post_service: BlogPostServiceDep
) -> IdentityResponseDto:
    create_blog_post_result = await blog_post_service.create_blog_post(
        dto.to_input(), auth_user
    )
    return IdentityResponseDto(identity=create_blog_post_result.identity)


@blog_post_router.put("/{blog_post_identity}")
async def update_blog_post(
    blog_post_identity: UUID,
    dto: BlogPostDto,
    auth_user: AuthUserDep,
    blog_post_service: BlogPostServiceDep,
) -> EmptyResponseDto:
    await blog_post_service.update_blog_post(blog_post_identity, dto.to_input(), auth_user)
    return EmptyResponseDto()


@blog_post_router.delete("/{blog_post_identity}")
async def delete_blog_post(
    blog_post_identity: UUID, auth_user: AuthUserDep, blog_post_service: BlogPostServiceDep
) -> EmptyResponseDto:
    await blog_post_service.delete_blog_post(blog_post_identity, auth_user)
    return EmptyResponseDto()
```

`app_factory.py` is the only file that knows the full list of domains.

## Database

Tables, Orm classes, and migrations follow `database.md`. This section covers how
application code uses the database.

- Async throughout: `AsyncSession`, `async_sessionmaker`, async driver. Never a sync
  `Session`.
- The engine is created once in `lifespan`, and the session factory once from it with
  `create_db_session_factory(db_engine)`. Never build an `async_sessionmaker` by hand;
  the factory carries the session options and the soft-delete rule. Db sessions are
  per-request.
- A service may import any Orm it needs; the domain boundary applies to services, not
  tables.
- Python code handles aware UTC datetimes only: `datetime.now(UTC)`
  (`database.md` › Timestamps).
- Deleting a row means setting `deleted_at` and `deleted_by_id`, never `DELETE`. ORM
  selects already exclude soft-deleted rows (`database.md` › Soft delete).
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
    async def find_user_by_email(self, email: str) -> FindUserByEmailResult:
        query = (
            select(UserOrm)
            .where(UserOrm.email == email)
            .options(selectinload(UserOrm.personas))
        )
        query_result = await self._db_session.execute(query)
        user_record = query_result.scalar_one_or_none()

        if user_record is None:
            raise NotFoundException("User not found")
        return FindUserByEmailResult.model_validate(user_record, from_attributes=True)
```

A record becomes a `Result` through `model_validate(<entity>_record, from_attributes=True)`,
which copies only the fields the `Result` declares, including nested `Result`s. The
flag goes on the call; a `Result` class never sets `model_config`, so it stays a plain
shape.

`scalar_one_or_none()` then raise `NotFoundException` for a single row,
`scalars().all()` for a list, which is empty rather than an error when nothing
matches.

Creates use `add()` then `flush()`, never `commit()`. `flush()` populates the primary
key and other server-side defaults:

```python
    async def create_user(self, user_input: CreateUserInput) -> CreateUserResult:
        user_record = UserOrm(
            email=user_input.email,
            display_name=user_input.display_name,
        )
        self._db_session.add(user_record)
        await self._db_session.flush()

        return CreateUserResult.model_validate(user_record, from_attributes=True)
```

Updates: load the Orm, mutate attributes, `flush()`. Use `update()` statements only
for bulk operations. Deletes are updates too: set `deleted_at` and `deleted_by_id`.

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

Code raises plain Python exceptions. Only `apps/api/core/exception_handlers.py` knows
status codes.

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
  (`UserService` → `UserEmailTakenException`, `GenerateTextService` →
  `GenerateTextInappropriateException`).
- **Parent**: exactly one standard exception, which is where its status code comes
  from. Never subclass `Exception` directly.
- **Domain base**: `<Domain>Exception(Exception)`, only if something catches every
  exception from that domain. A domain base never subclasses a standard exception.
  Specific exceptions list it first:
  `class GenerateTextInappropriateException(GenerateTextException, UnprocessableException)`.

```python
# libs/users/exceptions.py
class UserEmailTakenException(ConflictException): ...
```

Raise a standard exception directly when its category says everything:
`raise NotFoundException(f"Blog post {blog_post_identity} not found")`. Declare a lib
exception when code or a test needs to tell it apart from others in its category.

A `find_` method for a single row raises `NotFoundException` when the row is missing,
never returns `None`, so the route that calls it stays one line. That holds for
lookups only other services use too: a caller that expects absence catches the
exception.

### Mapping to status codes

`apps/api/core/exception_handlers.py` maps each standard exception to its status code,
and `register_exception_handlers()` registers one handler per entry. `create_app()`
calls it and does nothing else with exceptions. Starlette looks up handlers along the exception's class hierarchy,
so every lib exception gets its parent's status code without an entry of its own.

```python
# apps/api/core/exception_handlers.py
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


def register_exception_handlers(fastapi_app: FastAPI) -> None:
    for exception_class, status_code in STATUS_CODE_BY_EXCEPTION.items():
        fastapi_app.add_exception_handler(exception_class, build_exception_handler(status_code))
```

```python
# apps/api/app_factory.py
def create_app() -> FastAPI:
    fastapi_app = FastAPI(lifespan=lifespan)
    register_exception_handlers(fastapi_app)
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
