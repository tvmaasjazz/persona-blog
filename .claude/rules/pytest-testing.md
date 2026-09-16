---
paths:
  - "backend/tests/**/*.py"
---

# Tests

pytest, run from `backend/`. A test goes through the same entry points production
uses: a service built with its `__init__`, a route called over HTTP, and real Postgres
and Redis. Nothing is patched.

The whole backend has one suite, `backend/tests/`, because `backend/` is one project
with one `pyproject.toml`. Separate apps and libs are kept apart by folders and
`conftest.py` scope, not separate suites. If an app or lib ever becomes its own
package with its own `pyproject.toml`, its tests move into that package.

Examples leave out imports. Names that `plan.md` settles (`GenerateTextService`,
`GenerateTextResult`, `LlmService`, `LlmCompletionResult`, `UserService`,
`UserOrm`) are real. Others, like `LlmCompletionInput`, `LlmUnavailableException` and
`AuthSessionService`, are placeholders until their step lands.

## Stack

| Tool                                 | For                                                             |
| ------------------------------------ | --------------------------------------------------------------- |
| `pytest`                             | Runner, fixtures, parametrize                                   |
| `pytest-asyncio`                     | `async def` tests and fixtures                                  |
| `httpx`                              | `ASGITransport` to call the app, `MockTransport` to fake third-party HTTP |
| `structlog.testing`                  | Capturing log events                                            |
| Postgres + Redis from docker compose | Database and cache tests. Never SQLite, never fakeredis          |

Don't add other test dependencies without asking. That includes `pytest-mock`,
`respx`, `factory_boy`, `freezegun`, `pytest-env` and `asgi-lifespan`. Each one has an
in-house pattern below.

## Layout

```
backend/tests/
├── conftest.py              # shared by every app and lib: environment, settings, db, redis
├── factories/
│   └── users.py             # build_* and insert_*_row for one lib domain
├── stubs/
│   ├── http.py              # HttpHandlerStub
│   └── llm.py               # LlmServiceStub
├── payloads/
│   └── openai.py            # third-party response bodies, as builder functions
├── libs/
│   └── users/
│       ├── conftest.py      # only if the domain's lib tests share fixtures
│       ├── test_services.py
│       └── test_prompts.py
├── api/
│   ├── conftest.py          # app fixtures: fastapi_app, api_client, signed_in_user
│   ├── core/
│   │   ├── test_config.py
│   │   ├── test_exception_handlers.py
│   │   └── test_dependencies.py
│   ├── users/
│   │   ├── conftest.py
│   │   └── test_router.py
│   └── test_lifespan.py
└── migrations/
    ├── conftest.py
    └── test_revisions.py
```

- The test tree mirrors the source tree:
  - `libs/<domain>/<module>.py` → `tests/libs/<domain>/test_<module>.py`
  - `apps/api/domains/<domain>/<module>.py` → `tests/api/<domain>/test_<module>.py`
  - `apps/api/<module>.py` → `tests/api/test_<module>.py`
  - A second app gets `tests/<app_name>/`.
- Filenames are short, like source filenames: `tests/api/users/test_router.py`, never
  `test_users_router.py`. `--import-mode=importlib` allows the same basename in more
  than one folder.
- No `__init__.py` anywhere under `tests/`.
- A test module never imports from another test module or from a `conftest.py`.
  Shared code lives in `factories/`, `stubs/`, or `payloads/`, imported as
  `from tests.stubs.llm import LlmServiceStub`.
- `factories/` and `stubs/` have one module per lib domain, named after the lib
  package. `tests/stubs/llm.py` stubs `libs/llm/`. `payloads/` has one module per
  third-party provider.

## What to write for each source file

| Source                               | Test file                              | Required cases |
| ------------------------------------ | -------------------------------------- | -------------- |
| `libs/<d>/services.py`               | `tests/libs/<d>/test_services.py`      | For each public method: happy path, each branch, each exception it raises, each collaborator failure it handles. With a database, also persisted state, not found, constraint violations, related rows loaded (§2, §3) |
| `libs/<d>/prompts.py`                | `tests/libs/<d>/test_prompts.py`       | Each builder: the arguments appear in the output (§1) |
| `libs/<d>/inputs.py`, `results.py`   | `tests/libs/<d>/test_inputs.py`, `test_results.py` | Only models with a validator or declared constraint: accepted and rejected values (§1) |
| Class with an enum dispatch map      | That class's test file                 | Every enum member has a handler (§1) |
| `apps/api/domains/<d>/router.py`     | `tests/api/<d>/test_router.py`         | For each route: happy path, 422 per declared constraint, each exception the service raises, 401 if protected, persisted state for writes (§6) |
| `apps/api/domains/<d>/dtos.py`, `apps/api/core/dtos.py` | None, unless a mapper has logic | Route tests cover plain field copying |
| `apps/api/domains/<d>/dependencies.py` | None                                 | Route tests run the real factories |
| `apps/api/core/dependencies.py`      | `tests/api/core/test_dependencies.py`  | Session discards writes, transaction commits and rolls back, auth guard cases (§7) |
| `apps/api/core/config.py`            | `tests/api/core/test_config.py`        | TOML beats default, env beats TOML, missing secret fails (§8) |
| `apps/api/core/exception_handlers.py` | `tests/api/core/test_exception_handlers.py` | Each standard exception maps to its status; a lib exception gets its parent's; unhandled errors return 500 without internals (§7) |
| `libs/core/exceptions.py`, `libs/<d>/exceptions.py` | None                   | The app factory tests and the service tests that raise them cover these |
| `apps/api/lifespan.py`               | `tests/api/test_lifespan.py`           | Resources created at startup and closed at shutdown (§7) |
| Middleware                           | `tests/api/test_<module>.py`           | Observable effect on a real route (§9) |
| `libs/database/orm/*.py`             | None                                   | Service database tests cover them; CI's drift check catches mismatches with migrations |
| `migrations/`                        | `tests/migrations/test_revisions.py`   | One file covers every revision (§10) |
| `settings.py`, `constants.py`        | None                                   | — |

## Conventions for every test

### Naming

- A test function is named `test_<unit>_<condition>_<outcome>`. Leave out
  `<condition>` for the default path. `<unit>` is the service method or route handler
  name.
  - `test_create_user_returns_created_user`
  - `test_create_user_email_taken_raises_user_email_taken_exception`
  - `test_generate_text_unknown_text_type_returns_422`
- No test classes. Group tests by file and by the `<unit>` prefix.
- A fixture is a noun, named exactly like the production object it stands for:
  `db_session`, `redis_client`, `app_settings`, `fastapi_app`, `api_client`. Never a
  `test_`, `get_`, or `mock_` prefix.
- `python-naming.md` applies in full, so write `create_user_response`, not
  `response`, and `user_query_result`, not `result`.
- A stub class is named `<Class>Stub`, e.g. `LlmServiceStub`.
- A named expected value is `expected_<thing>`.

### Shape of a test

Arrange, act, assert: three blocks separated by blank lines, with no `# Arrange`
comments. The act block is the single call under test. If the assert block needs a
value pulled out of the result first, that line starts the assert block.

Test one behaviour per test. Several asserts are fine when they describe the same
outcome; a second action belongs in a second test.

Write expected values as literals in the test, never recomputed with the code's own
logic: `character_count=19`, not `len(content)`. The no-loose-literals rule covers
`libs/` and `apps/`, not tests. Test data should be visible where it's asserted.

When behaviour depends on a setting, build the settings model in the test with a
non-default value, e.g. `HumanizerSettings(max_rewrite_passes=2)`. Never rely on the
default.

### Assertions

- Use plain `assert`. pytest shows both sides when it fails.
- Compare whole objects: `assert create_user_result == CreateUserResult(...)` and
  `assert create_user_response.json() == {...}`. Whole-object equality catches added,
  missing and leaked fields. Field-by-field asserts don't.
- If the test can't know a value (like a server timestamp), take it from the seeded
  row. Failing that, use `unittest.mock.ANY`. `ANY` is the only import allowed from
  `unittest.mock`.
- Assert exceptions with `with pytest.raises(UserEmailTakenException):`. Add `match=`
  only when the message is part of the contract, such as user-facing text.
- Compare floats with `pytest.approx`.
- Don't assert on log wording, exception messages, or FastAPI's validation `msg`.

### Parametrize

Use `@pytest.mark.parametrize` when cases differ only in data. Argument names go in a
tuple, and every case is a `pytest.param` with a snake_case `id` (§6 has an example).
The one exception is iterating an enum: `list(TextType)` can be passed as is,
because the member values serve as ids.

Cases that need different setup are separate tests. A test body never branches on a
parameter.

The two-calls-per-statement limit from `python-naming.md` doesn't count the
`pytest.param(...)` entries in a parametrize list. Each entry still stays under two
calls.

### Fixtures

- Function scope is the default. Use `scope="session"` only for expensive resources
  that never change: `app_settings`, `db_engine`. Never `module` or `class` scope.
- A fixture with setup and teardown is a `yield` fixture. Never
  `request.addfinalizer`.
- Type the return: `-> AsyncSession`, or `-> AsyncIterator[AsyncSession]` for a yield
  fixture.
- Where a fixture lives depends on who uses it:
  - one test module → that module
  - one domain → that domain's `conftest.py`
  - several domains of one app, or the lib tests → `tests/<app>/conftest.py` or
    `tests/libs/conftest.py`
  - every app and lib → `tests/conftest.py`. Only infrastructure goes here:
    environment, settings, database, Redis. App fixtures never do, so lib tests
    can't reach the app.
- `autouse=True` is allowed in exactly two places:
  - the root `environment_variables` fixture
  - a domain conftest's override of a third-party boundary, so no test in that
    folder can reach the real API
- When a fixture is only needed for its side effect, request it with
  `@pytest.mark.usefixtures("signed_in_user")`, not as an unused argument.
- Test data is not a fixture. Build any value a test asserts on inside that test,
  with a `factories/` function. The one shared data fixture is `signed_in_user` (§6),
  because signing in is setup, not the thing under test.

### Async

- `asyncio_mode = "auto"` is on, so write `async def test_...` without
  `@pytest.mark.asyncio`.
- All tests and fixtures share one session-wide event loop (see Configuration). A
  session-scoped async engine used from a per-test loop fails with "attached to a
  different loop".
- Never use `asyncio.run()`, `loop.run_until_complete()`, `time.sleep()`, or
  `asyncio.sleep()` in a test. If a test has to wait for something, it isn't
  controlling that thing.
- A forgotten `await` produces a `RuntimeWarning`, and the config turns warnings into
  failures. That's the main reason warnings are errors.

### Test doubles

Use stubs, never mocks.

| Collaborator                        | Double                                                        |
| ----------------------------------- | ------------------------------------------------------------- |
| One of our services                 | Hand-written `<Class>Stub` in `tests/stubs/<domain>.py`       |
| Third-party HTTP API                | The real SDK client over `httpx.MockTransport` (§4)           |
| Postgres, Redis                     | The real thing                                                |
| Anything reachable only by patching | Nothing. Report it: the code has a hidden dependency to fix   |

- `unittest.mock.patch`, `MagicMock`, `AsyncMock`, and `monkeypatch.setattr` are
  banned. Needing one means the code should take that dependency through `__init__`
  or a dependency factory.
- Use `monkeypatch` only for environment variables (`setenv`, `delenv`) and
  `chdir`.

How to write a stub:

- Subclass the real class and override only the public methods tests need.
- Never call `super().__init__()`. A method that isn't overridden then fails loudly
  instead of doing real work.
- Name the stub's attributes `<method>_` plus what they hold:
  - `<method>_inputs`: every input received, in order
  - `<method>_result`: the value to return
  - `<method>_results`: values popped in order, for when calls must differ (such as a
    rewrite loop)
  - `<method>_error`: an exception to raise instead

```python
# tests/stubs/llm.py
class LlmServiceStub(LlmService):
    def __init__(self) -> None:
        self.complete_inputs: list[LlmCompletionInput] = []
        self.complete_result = build_llm_completion_result()
        self.complete_error: Exception | None = None

    async def complete(self, llm_completion_input: LlmCompletionInput) -> LlmCompletionResult:
        self.complete_inputs.append(llm_completion_input)
        if self.complete_error is not None:
            raise self.complete_error
        return self.complete_result
```

### Test data

Test data comes from `tests/factories/<domain>.py`, one module per lib domain:

- `build_<model>(...)` returns an `Input`, a `Result`, or an unsaved `Orm`. Sync.
- `insert_<entity>_row(db_session, ...)` adds and flushes an `Orm` and returns it.
  Async. It bypasses services, so a test of one service never depends on another
  service working.
- Every parameter is keyword-only with a valid default, so a test passes only the
  values it asserts on. Unique columns default to a fresh value.
- Write out keyword parameters, never `**overrides`, so a typo fails.

```python
# tests/factories/users.py
def build_create_user_input(
    *, email: str | None = None, display_name: str = "Ada Lovelace"
) -> CreateUserInput:
    return CreateUserInput(email=email or _build_unique_email(), display_name=display_name)


async def insert_user_row(
    db_session: AsyncSession, *, email: str | None = None, display_name: str = "Ada Lovelace"
) -> UserOrm:
    user_orm = UserOrm(email=email or _build_unique_email(), display_name=display_name)
    db_session.add(user_orm)
    await db_session.flush()
    return user_orm


def _build_unique_email() -> str:
    return f"user-{uuid4().hex}@example.com"
```

### Determinism

- Tests pass in any order and on their own. No module-level mutable state.
- No network except local Postgres and Redis.
- No wall clock in assertions. Assert that a TTL is within bounds or that a timestamp
  is not `None`. If behaviour depends on "now", stop and report it: the code needs an
  injected clock.
- No randomness, apart from the unique-value defaults in factories.

### What not to test

- Framework behaviour: Pydantic coercing types, `frozen=True` freezing, FastAPI
  rejecting a missing body. Test only constraints this codebase declares.
- Setting defaults and constant values.
- `_private` methods directly. Test them through the public method that uses them.
  The one exception is an enum dispatch map (§1).
- Dependency factories and `Annotated` aliases directly, since route tests run them.
- `to_input()` / `from_result()` directly, unless they do more than copy fields.

## Configuration

```toml
# backend/pyproject.toml
[tool.pytest]
testpaths = ["tests"]
pythonpath = ["."]
addopts = ["--import-mode=importlib", "-m", "not live_llm and not migration"]
strict = true
filterwarnings = ["error"]
markers = [
    "live_llm: calls the real LLM provider; run by hand with -m live_llm",
    "migration: rebuilds the test database schema; run with -m migration",
]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"
asyncio_default_test_loop_scope = "session"
```

- `[tool.pytest]` is pytest 9's native TOML table. Don't use
  `[tool.pytest.ini_options]`.
- `strict = true` turns on every strictness option, so an unregistered marker, a
  mistyped config key, or a duplicate parametrize id fails the run. It's safe here
  because `uv.lock` pins pytest.
- `filterwarnings = ["error"]` turns warnings into failures. For a third-party
  warning we can't fix, add a specific `"ignore:<message>:<Category>"` line with a
  comment saying why. Never a blanket ignore.
- The default `-m` expression deselects live and migration tests. Passing `-m` on the
  command line replaces it.

## Root fixtures

Each fixture arrives with the plan step that adds its resource (the app in step 5,
the database and Redis in step 6, `signed_in_user` in step 9). The code below is the
target shape.

`tests/conftest.py` holds infrastructure every app and lib uses:

```python
# tests/conftest.py
TEST_ENVIRONMENT_VARIABLES = {
    "ENVIRONMENT": "TEST",
    "DATABASE_URL": "postgresql+asyncpg://pb:pb@localhost:5437/pb_test",
    "REDIS_URL": "redis://localhost:6387/15",
    "OPENAI_API_KEY": "test-openai-api-key",
}
TEST_DATABASE_NAME_SUFFIX = "_test"
TEST_REDIS_DB_INDEX = 15


@pytest.fixture(scope="session", autouse=True)
def environment_variables() -> Iterator[None]:
    with pytest.MonkeyPatch.context() as session_monkeypatch:
        for variable_name, variable_value in TEST_ENVIRONMENT_VARIABLES.items():
            session_monkeypatch.setenv(variable_name, variable_value)
        yield


@pytest.fixture(scope="session")
def app_settings() -> AppSettings:
    return AppSettings()


@pytest.fixture(scope="session")
async def db_engine(
    app_settings: AppSettings, pytestconfig: pytest.Config
) -> AsyncIterator[AsyncEngine]:
    database_url = make_url(app_settings.database_url)
    if database_url.database is None or not database_url.database.endswith(
        TEST_DATABASE_NAME_SUFFIX
    ):
        raise RuntimeError(f"Refusing to reset non-test database {database_url.database!r}")

    db_engine = create_async_engine(database_url)
    async with db_engine.begin() as db_connection:
        await db_connection.execute(text("DROP SCHEMA public CASCADE"))
        await db_connection.execute(text("CREATE SCHEMA public"))
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=pytestconfig.rootpath,
        check=True,
    )
    yield db_engine
    await db_engine.dispose()


@pytest.fixture
async def db_connection(db_engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    async with db_engine.connect() as db_connection:
        outer_transaction = await db_connection.begin()
        yield db_connection
        await outer_transaction.rollback()


@pytest.fixture
def db_session_factory(db_connection: AsyncConnection) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=db_connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )


@pytest.fixture
async def db_session(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with db_session_factory() as db_session:
        yield db_session


@pytest.fixture
async def redis_client(app_settings: AppSettings) -> AsyncIterator[Redis]:
    redis_client = Redis.from_url(app_settings.redis_url)
    if redis_client.connection_pool.connection_kwargs.get("db") != TEST_REDIS_DB_INDEX:
        raise RuntimeError("Refusing to flush a non-test Redis database")
    await redis_client.flushdb()
    yield redis_client
    await redis_client.flushdb()
    await redis_client.aclose()
```

`tests/api/conftest.py` holds the app fixtures. Only tests under `tests/api/` can see
them. `signed_in_user` (§6) lives here too.

```python
# tests/api/conftest.py
@pytest.fixture
async def fastapi_app(
    db_session_factory: async_sessionmaker[AsyncSession], redis_client: Redis
) -> AsyncIterator[FastAPI]:
    fastapi_app = create_app()
    async with fastapi_app.router.lifespan_context(fastapi_app):
        fastapi_app.state.db_session_factory = db_session_factory
        yield fastapi_app


@pytest.fixture
async def api_client(fastapi_app: FastAPI) -> AsyncIterator[AsyncClient]:
    api_transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=api_transport, base_url="https://test") as api_client:
        yield api_client
```

What these fixtures guarantee:

- **Real migrations.** `db_engine` wipes the schema and runs the real migrations once
  per session. Tests run against the schema the migrations build, never
  `Base.metadata.create_all()`, so a broken `.up.sql` fails the suite.
- **Rollback per test.** Each test gets one connection inside an outer transaction
  that's rolled back at teardown. `join_transaction_mode="create_savepoint"` turns
  every session's `begin()` and `commit()` into a savepoint, so services and routes
  that commit still leave nothing behind. Every other session option must match
  `libs/database/session.py`.
- **Real lifespan.** `fastapi_app` runs the real lifespan, because httpx's
  `ASGITransport` never sends lifespan events. It then points
  `app.state.db_session_factory` at the test connection. Each request still opens its
  own session through the real `get_db_session` or `get_db_transaction`, so a write
  route wired to `DbSessionDep` loses its write in tests, just as in production.
- **No leaked overrides.** `fastapi_app` is function-scoped, so `dependency_overrides`
  never carry over between tests and never need clearing. It also requests
  `redis_client`, so every route test starts with an empty Redis.
- **Secure cookies work.** `base_url="https://test"` lets httpx's cookie jar send
  `secure` cookies back.
- **Guards.** Resetting a database whose name doesn't end in `_test`, or flushing a
  Redis index other than 15, raises.

Before running tests, start docker compose (`docker compose up -d`). The
`pb_test` database comes from the compose init script locally and from the
service container in CI, which uses the same URLs. Tests never create or drop
databases.

## §1 Pure unit tests

These are sync tests with no fixtures, covering prompts, model validators, enum
dispatch maps, and DTO mappers that contain logic.

| Situation                          | Pattern |
| ---------------------------------- | ------- |
| Prompt builder                     | Call it with distinctive argument values and assert each one appears. Never snapshot the whole prompt |
| Template placeholder never filled  | Calling every builder once covers it, because `.format()` raises `KeyError` |
| Validator or `Field` constraint    | One parametrized test of accepted values, one of rejected values raising `ValidationError` |
| Enum dispatch map                  | Parametrize over every member and assert each has a handler. The only allowed read of a `_private` attribute |
| DTO mapper with logic              | Build the DTO, call the mapper, compare the whole returned model |

```python
# tests/libs/generate_text/test_prompts.py
def test_build_user_prompt_includes_prompt_text() -> None:
    user_prompt = GenerateTextPrompt.build_user_prompt(
        prompt_text="a post about sourdough starters",
        text_type=TextType.BLOG_POST,
    )

    assert "a post about sourdough starters" in user_prompt
```

```python
# tests/libs/users/test_inputs.py
@pytest.mark.parametrize(
    "display_name",
    [pytest.param("", id="empty"), pytest.param("   ", id="whitespace_only")],
)
def test_create_user_input_blank_display_name_raises_validation_error(display_name: str) -> None:
    with pytest.raises(ValidationError):
        build_create_user_input(display_name=display_name)
```

```python
@pytest.mark.parametrize("command_type", list(CommandType))
def test_execution_engine_has_handler_for_every_command_type(command_type: CommandType) -> None:
    execution_engine = ExecutionEngine()

    assert command_type in execution_engine._dispatch_map
```

## §2 Service tests

Build the service directly with stubs and an explicit settings object. No app, no
HTTP. If construction takes a client stack, move it into a fixture in the domain's
`conftest.py`.

| Situation                         | Pattern |
| --------------------------------- | ------- |
| Happy path                        | Configure stubs, call the method, compare the whole `Result` |
| Collaborator gets the right input | Assert the stub's `<method>_inputs == [expected_input]` |
| Collaborator raises               | Set the stub's `<method>_error`, then `pytest.raises` whatever the service is meant to raise |
| One branch per enum member or flag | One test per branch, or parametrize if only data differs |
| Behaviour driven by a setting     | Build the settings model with a non-default value in the test |
| Loop or retry bound               | Queue results that never meet the exit condition; assert the call count equals the setting |
| Needs the database                | Same file, see §3 |

```python
# tests/libs/generate_text/test_services.py
async def test_generate_text_returns_content_and_character_count() -> None:
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="Sourdough is alive.")
    generate_text_service = GenerateTextService(llm_service=llm_service_stub)
    generate_text_input = build_generate_text_input()

    generate_text_result = await generate_text_service.generate_text(generate_text_input)

    assert generate_text_result == GenerateTextResult(
        content="Sourdough is alive.",
        character_count=19,
    )


async def test_generate_text_llm_unavailable_raises_llm_unavailable_exception() -> None:
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_error = LlmUnavailableException()
    generate_text_service = GenerateTextService(llm_service=llm_service_stub)
    generate_text_input = build_generate_text_input()

    with pytest.raises(LlmUnavailableException):
        await generate_text_service.generate_text(generate_text_input)
```

## §3 Database tests

These are service tests that take the `db_session` fixture. They hit real Postgres,
rolled back after each test.

| Situation                         | Pattern |
| --------------------------------- | ------- |
| Create                            | Call, then `select()` the row back and assert on it. The returned `Result` alone proves nothing about persistence |
| Primary key and server defaults   | Assert `id` is set and `created_at is not None`. Never assert an exact timestamp |
| Read, found                       | `insert_*_row`, call, compare the whole `Result` built from the row's values |
| Read, not found                   | Call with a key that was never inserted and assert the result `is None` |
| Update                            | Insert, call, select back, and assert both the changed and unchanged columns |
| Unique, foreign-key, or check constraint | Insert the conflicting row first, then `pytest.raises` the lib or standard exception the service raises. The session can't be used afterwards, so the test ends at the `with` block |
| Relationships                     | Insert the parent and at least one child, and assert the child appears. A missing `selectinload()` fails as `MissingGreenlet` |
| Lists                             | Insert rows out of order. If the method promises an order, assert the exact list; otherwise compare sorted |
| Enum column                       | Parametrize a write-and-read round trip over every member |
| Service that commits              | No special handling. The commit only releases a savepoint |
| Failure partway through a write   | Trigger the failure, then select and assert no partial rows |

```python
# tests/libs/users/test_services.py
async def test_create_user_persists_row(db_session: AsyncSession) -> None:
    user_service = UserService(db_session=db_session)
    create_user_input = build_create_user_input(email="ada@example.com")

    create_user_result = await user_service.create_user(create_user_input)

    user_query = select(UserOrm).where(UserOrm.id == create_user_result.id)
    user_orm = await db_session.scalar(user_query)
    assert user_orm is not None
    assert user_orm.email == "ada@example.com"


async def test_create_user_email_taken_raises_user_email_taken_exception(
    db_session: AsyncSession,
) -> None:
    await insert_user_row(db_session, email="ada@example.com")
    user_service = UserService(db_session=db_session)
    create_user_input = build_create_user_input(email="ada@example.com")

    with pytest.raises(UserEmailTakenException):
        await user_service.create_user(create_user_input)


async def test_get_user_by_email_includes_personas(db_session: AsyncSession) -> None:
    user_orm = await insert_user_row(db_session, email="ada@example.com")
    await insert_persona_row(db_session, user_id=user_orm.id, name="Baker Bea")
    user_service = UserService(db_session=db_session)

    get_user_by_email_result = await user_service.get_user_by_email("ada@example.com")

    assert get_user_by_email_result is not None
    assert [persona.name for persona in get_user_by_email_result.personas] == ["Baker Bea"]
```

Link child rows by foreign key (`user_id=`), never with `parent.children.append()`.
Appending triggers a lazy load in async code.

## §4 Third-party HTTP APIs

Use the real SDK client, built over `httpx.MockTransport`. The handler receives the
actual `httpx.Request` the SDK built, so one test checks both what we send and how we
parse the reply.

| Situation                         | Pattern |
| --------------------------------- | ------- |
| Success                           | Queue a response built from `tests/payloads/<provider>.py` and compare the whole `Result` |
| Request shape                     | Read `handle_requests[0]` and assert the path, plus body fields that come from settings (model, max tokens) |
| 4xx or 5xx                        | Parametrize the status code, queue the provider's error body, `pytest.raises` the lib or standard exception the service raises |
| No hidden retries                 | On error cases, assert `len(handle_requests) == 1` |
| Timeout or connection failure     | Set `handle_error = httpx.ReadTimeout(...)` or `httpx.ConnectError(...)`, then `pytest.raises` the lib or standard exception the service raises |
| Malformed or partial body         | Build the payload with a field set to `None` or missing, then `pytest.raises` the lib or standard exception the service raises |
| Unexpected extra request          | No handling needed: `handle_responses.pop(0)` raises `IndexError` |

- Build SDK clients with `max_retries=0`. Otherwise every error case sleeps through
  the SDK's retry backoff.
- Payload builders copy a real captured response, with keyword parameters for the
  fields tests vary.

```python
# tests/stubs/http.py
class HttpHandlerStub:
    def __init__(self) -> None:
        self.handle_requests: list[httpx.Request] = []
        self.handle_responses: list[httpx.Response] = []
        self.handle_error: Exception | None = None

    def handle(self, http_request: httpx.Request) -> httpx.Response:
        self.handle_requests.append(http_request)
        if self.handle_error is not None:
            raise self.handle_error
        return self.handle_responses.pop(0)
```

```python
# tests/libs/llm/conftest.py
@pytest.fixture
def openai_handler_stub() -> HttpHandlerStub:
    return HttpHandlerStub()


@pytest.fixture
async def llm_service(openai_handler_stub: HttpHandlerStub) -> AsyncIterator[LlmService]:
    openai_transport = httpx.MockTransport(openai_handler_stub.handle)
    async with httpx.AsyncClient(transport=openai_transport) as openai_http_client:
        llm_client = AsyncOpenAI(
            api_key="test-openai-api-key",
            http_client=openai_http_client,
            max_retries=0,
        )
        llm_settings = LlmSettings(model_name="test-model")
        yield LlmService(llm_client=llm_client, llm_settings=llm_settings)
```

```python
# tests/libs/llm/test_services.py
async def test_complete_sends_model_from_settings_and_returns_token_counts(
    llm_service: LlmService, openai_handler_stub: HttpHandlerStub
) -> None:
    openai_payload = build_openai_chat_completion_payload(
        content="Sourdough is alive.", prompt_tokens=12, completion_tokens=5
    )
    openai_handler_stub.handle_responses.append(httpx.Response(200, json=openai_payload))
    llm_completion_input = build_llm_completion_input()

    llm_completion_result = await llm_service.complete(llm_completion_input)

    sent_request_body = json.loads(openai_handler_stub.handle_requests[0].content)
    assert sent_request_body["model"] == "test-model"
    assert llm_completion_result == LlmCompletionResult(
        content="Sourdough is alive.", input_tokens=12, output_tokens=5
    )


@pytest.mark.parametrize("status_code", [401, 429, 500])
async def test_complete_error_status_raises_llm_unavailable_exception(
    llm_service: LlmService, openai_handler_stub: HttpHandlerStub, status_code: int
) -> None:
    openai_error_payload = build_openai_error_payload()
    openai_handler_stub.handle_responses.append(
        httpx.Response(status_code, json=openai_error_payload)
    )
    llm_completion_input = build_llm_completion_input()

    with pytest.raises(LlmUnavailableException):
        await llm_service.complete(llm_completion_input)

    assert len(openai_handler_stub.handle_requests) == 1
```

## §5 Redis

These tests take the `redis_client` fixture: real Redis, database index 15, flushed
before and after each test.

| Situation                  | Pattern |
| -------------------------- | ------- |
| Key written                | Call, then read the key back with `redis_client.get` and assert the stored value |
| TTL set                    | Bind `await redis_client.ttl(key)` and assert `0 < ttl <= <setting value>` |
| Expired key                | Delete the key, which is what expiry looks like to the service. Call and assert it's treated as missing. Never sleep |
| Delete (logout)            | Call, bind `await redis_client.exists(key)`, assert `0` |
| Counter below, at, over a cap | Pre-set the counter with `redis_client.set(key, n)`, call, and assert allowed or `pytest.raises` the lib exception (a `RateLimitedException` subclass) |
| Exempt user                | Counter at the cap with an exempt user; assert allowed |
| Key and cookie names       | Assert the literal (`"session:..."`), not the imported constant. These `constants.py` values must match deployed data, and a test that reuses the constant can't catch a change |

```python
# tests/libs/auth/test_services.py
async def test_create_session_stores_user_id_with_ttl(redis_client: Redis) -> None:
    auth_settings = AuthSettings(session_ttl_seconds=600)
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=auth_settings
    )

    session_id = await auth_session_service.create_session(user_id=42)

    stored_user_id = await redis_client.get(f"session:{session_id}")
    session_ttl_seconds = await redis_client.ttl(f"session:{session_id}")
    assert stored_user_id == b"42"
    assert 0 < session_ttl_seconds <= 600
```

## §6 Route tests

These use `api_client` against the real app, with real dependency factories and the
real session factory.

**Override only the lowest dependency that reaches a third party** (such as
`get_llm_service` or the Google token verifier's factory), never the service the
route calls. That way the domain's `dependencies.py` still runs for real. If no such
dependency exists because the domain factory builds a third-party client inline,
report it and propose splitting it out.

Put the override in the domain's `conftest.py` as an `autouse` fixture:

```python
# tests/api/generate_text/conftest.py
@pytest.fixture(autouse=True)
def llm_service_stub(fastapi_app: FastAPI) -> LlmServiceStub:
    llm_service_stub = LlmServiceStub()
    fastapi_app.dependency_overrides[get_llm_service] = lambda: llm_service_stub
    return llm_service_stub
```

**Signed-in requests go through the real guard.** Never override `get_current_user`.

```python
# tests/api/conftest.py
@pytest.fixture
async def signed_in_user(
    api_client: AsyncClient,
    db_session: AsyncSession,
    redis_client: Redis,
    app_settings: AppSettings,
) -> UserOrm:
    user_orm = await insert_user_row(db_session)
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=app_settings.auth
    )
    session_id = await auth_session_service.create_session(user_id=user_orm.id)
    api_client.cookies.set("sid", session_id)
    return user_orm
```

| Situation                     | Pattern |
| ----------------------------- | ------- |
| Happy path                    | Send raw JSON; assert the status and the whole `response.json()` |
| Wire format                   | Request bodies and expected responses are dict literals, never `Dto(...).model_dump()`. The test is what pins the JSON contract |
| Validation → 422              | Parametrize one missing required field plus one case per constraint the DTO declares. Assert the status and `detail[0]["loc"]`, never the message |
| Exception → status            | Set up the real condition (insert the duplicate row), or set the stub's `<method>_error`. Assert the status and the `{"detail": ...}` body |
| Create (`POST`)               | Select the row by the returned `identity` and assert its columns. The body is `{"identity": "<id>"}` |
| Update (`PUT`) or `DELETE`    | Assert the body `== {}`, then select to prove the row changed or is gone |
| Write persists                | After a 2xx, select the row through `db_session`. This catches a write route wired to `DbSessionDep` |
| List (`GET` with a `FetchAllQueryDto`) | An invalid query value → 422 with `loc` starting `"query"`. Pagination and filter cases wait on the conventions `fastapi-structure.md` hasn't settled yet |
| Write rolls back on failure   | Make the route fail after its first write; assert no row |
| Response hides internals      | Whole-body equality already covers it: an extra field like `google_subject_id` fails |
| Protected route, signed out   | One test per protected route using plain `api_client`; assert 401 |
| Protected route, signed in    | `@pytest.mark.usefixtures("signed_in_user")`, or request it to use the user's values |
| Invalid or expired session    | Covered once in `tests/api/core/test_dependencies.py`, not per route |
| Not found → 404               | Use an id that was never inserted |
| Redirect                      | httpx doesn't follow redirects by default. Assert the status, then check `Location` with `urllib.parse` |
| Set-Cookie attributes         | Read `response.headers.get_list("set-cookie")`; assert `HttpOnly`, `Secure` for the environment, and `SameSite` |
| Rate limit → 429              | Pre-set the Redis counter at the cap; assert 429 |
| Unhandled exception → 500     | Covered once in `tests/api/core/test_exception_handlers.py`, not per route |

```python
# tests/api/generate_text/test_router.py
@pytest.mark.usefixtures("signed_in_user")
async def test_generate_text_returns_generated_text_response(
    api_client: AsyncClient, llm_service_stub: LlmServiceStub
) -> None:
    llm_service_stub.complete_result = build_llm_completion_result(content="Sourdough is alive.")

    generate_text_response = await api_client.post(
        "/generate-text",
        json={"text_type": "BLOG_POST", "prompt_text": "a post about sourdough"},
    )

    assert generate_text_response.status_code == 200
    assert generate_text_response.json() == {
        "content": "Sourdough is alive.",
        "character_count": 19,
    }


@pytest.mark.usefixtures("signed_in_user")
@pytest.mark.parametrize(
    ("request_body", "expected_error_location"),
    [
        pytest.param(
            {"prompt_text": "sourdough"},
            ["body", "text_type"],
            id="missing_text_type",
        ),
        pytest.param(
            {"text_type": "HAIKU", "prompt_text": "sourdough"},
            ["body", "text_type"],
            id="unknown_text_type",
        ),
    ],
)
async def test_generate_text_invalid_body_returns_422(
    api_client: AsyncClient,
    request_body: dict[str, str],
    expected_error_location: list[str],
) -> None:
    generate_text_response = await api_client.post("/generate-text", json=request_body)

    response_body = generate_text_response.json()
    assert generate_text_response.status_code == 422
    assert response_body["detail"][0]["loc"] == expected_error_location


@pytest.mark.usefixtures("signed_in_user")
async def test_generate_text_llm_unavailable_returns_503(
    api_client: AsyncClient, llm_service_stub: LlmServiceStub
) -> None:
    llm_service_stub.complete_error = LlmUnavailableException()

    generate_text_response = await api_client.post(
        "/generate-text",
        json={"text_type": "BLOG_POST", "prompt_text": "a post about sourdough"},
    )

    assert generate_text_response.status_code == 503


async def test_generate_text_signed_out_returns_401(api_client: AsyncClient) -> None:
    generate_text_response = await api_client.post(
        "/generate-text",
        json={"text_type": "BLOG_POST", "prompt_text": "a post about sourdough"},
    )

    assert generate_text_response.status_code == 401
```

```python
# tests/api/blog_posts/test_router.py
@pytest.mark.usefixtures("signed_in_user")
async def test_create_blog_post_persists_row_and_returns_identity(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    create_blog_post_response = await api_client.post(
        "/blog-posts/", json={"title": "Starter care", "body": "Feed it daily."}
    )

    response_body = create_blog_post_response.json()
    blog_post_id = int(response_body["identity"])
    blog_post_orm = await db_session.get(BlogPostOrm, blog_post_id)
    assert create_blog_post_response.status_code == 200
    assert blog_post_orm is not None
    assert blog_post_orm.title == "Starter care"


@pytest.mark.usefixtures("signed_in_user")
async def test_update_blog_post_persists_changes(
    api_client: AsyncClient, db_session: AsyncSession
) -> None:
    blog_post_orm = await insert_blog_post_row(db_session, title="Draft title")

    update_blog_post_response = await api_client.put(
        f"/blog-posts/{blog_post_orm.id}",
        json={"title": "Final title", "body": "Feed it daily."},
    )

    title_query = select(BlogPostOrm.title).where(BlogPostOrm.id == blog_post_orm.id)
    persisted_title = await db_session.scalar(title_query)
    assert update_blog_post_response.status_code == 200
    assert update_blog_post_response.json() == {}
    assert persisted_title == "Final title"
```

## §7 App factory, lifespan, core dependencies

To test app-wide behaviour without a real domain route, add a throwaway route to the
test's `fastapi_app` inside the test body.

| File                    | Situation                            | Pattern |
| ----------------------- | ------------------------------------ | ------- |
| `test_exception_handlers.py` | Each standard exception → its status and `{"detail": message}` body | Parametrize one case per entry in `STATUS_CODE_BY_EXCEPTION`, written out as literals (never looped from the map). A throwaway route raises each one |
| `test_exception_handlers.py` | A lib exception → its parent's status | One test with one lib exception. That proves handler lookup follows the class hierarchy |
| `test_exception_handlers.py` | Unhandled exception → 500, no internals | Client built with `ASGITransport(..., raise_app_exceptions=False)`. By default httpx re-raises the exception into the test instead of returning the 500 |
| `test_lifespan.py`      | Startup creates resources            | Enter `lifespan_context` on a fresh `create_app()`; assert the `app.state` attributes |
| `test_lifespan.py`      | Shutdown closes them                 | After the `async with` exits, assert closed (`http_client.is_closed`) |
| `test_lifespan.py`      | Invalid settings fail startup        | `monkeypatch.setenv` a bad value; `pytest.raises(ValidationError)` around entering the lifespan |
| `test_dependencies.py`  | `get_db_session` discards writes     | A throwaway route with `DbSessionDep` inserts a row; select through `db_session` and assert it's absent |
| `test_dependencies.py`  | `get_db_transaction` commits         | Same, with `DbTransactionDep`; assert present |
| `test_dependencies.py`  | `get_db_transaction` rolls back on error | The route inserts, then raises. Wrap the request in `pytest.raises`, then assert the row is absent |
| `test_dependencies.py`  | Auth guard                           | No cookie, unknown session id, session for a deleted user: each 401. A valid session reaches the route |

```python
# tests/api/core/test_exception_handlers.py
@pytest.mark.parametrize(
    ("standard_exception", "expected_status_code"),
    [
        pytest.param(NotFoundException("Blog post 7 not found"), 404, id="not_found"),
        pytest.param(ConflictException("Email already taken"), 409, id="conflict"),
        pytest.param(RateLimitedException("Generation limit reached"), 429, id="rate_limited"),
    ],
)
async def test_exception_handler_maps_standard_exception_to_status_code(
    fastapi_app: FastAPI,
    api_client: AsyncClient,
    standard_exception: Exception,
    expected_status_code: int,
) -> None:
    @fastapi_app.get("/raise-standard-exception")
    async def raise_standard_exception() -> None:
        raise standard_exception

    raise_standard_exception_response = await api_client.get("/raise-standard-exception")

    assert raise_standard_exception_response.status_code == expected_status_code
    assert raise_standard_exception_response.json() == {"detail": str(standard_exception)}


async def test_exception_handler_gives_lib_exception_its_parent_status_code(
    fastapi_app: FastAPI, api_client: AsyncClient
) -> None:
    @fastapi_app.get("/raise-lib-exception")
    async def raise_lib_exception() -> None:
        raise UserEmailTakenException("Email already taken")

    raise_lib_exception_response = await api_client.get("/raise-lib-exception")

    assert raise_lib_exception_response.status_code == 409


async def test_unhandled_error_returns_500_without_internals(fastapi_app: FastAPI) -> None:
    @fastapi_app.get("/raise-unhandled-error")
    async def raise_unhandled_error() -> None:
        raise RuntimeError("secret-internal-detail")

    api_transport = ASGITransport(app=fastapi_app, raise_app_exceptions=False)
    async with AsyncClient(transport=api_transport, base_url="https://test") as api_client:
        raise_unhandled_error_response = await api_client.get("/raise-unhandled-error")

    assert raise_unhandled_error_response.status_code == 500
    assert "secret-internal-detail" not in raise_unhandled_error_response.text
```

```python
# tests/api/test_lifespan.py
async def test_lifespan_closes_http_client_on_shutdown() -> None:
    fastapi_app = create_app()

    async with fastapi_app.router.lifespan_context(fastapi_app):
        http_client: AsyncClient = fastapi_app.state.http_client

    assert http_client.is_closed
```

```python
# tests/api/core/test_dependencies.py
async def test_get_db_session_discards_uncommitted_writes(
    fastapi_app: FastAPI, api_client: AsyncClient, db_session: AsyncSession
) -> None:
    @fastapi_app.post("/insert-user-without-transaction")
    async def insert_user_without_transaction(request_db_session: DbSessionDep) -> None:
        await insert_user_row(request_db_session, email="ada@example.com")

    insert_user_response = await api_client.post("/insert-user-without-transaction")

    user_query = select(UserOrm).where(UserOrm.email == "ada@example.com")
    inserted_user_orm = await db_session.scalar(user_query)
    assert insert_user_response.status_code == 200
    assert inserted_user_orm is None
```

## §8 Settings

Tests live in `tests/api/core/test_config.py` and build `AppSettings()` directly
inside an isolated directory.

| Situation                   | Pattern |
| --------------------------- | ------- |
| TOML overrides the default  | Write `config.toml` into `tmp_path`, `monkeypatch.chdir(tmp_path)`, build, assert |
| Env var overrides TOML      | Same, plus `monkeypatch.setenv` for the same field |
| Nested field from env       | `monkeypatch.setenv("HUMANIZER__MAX_REWRITE_PASSES", "5")` and assert the nested value |
| Missing required secret     | `monkeypatch.delenv("OPENAI_API_KEY")`, then `pytest.raises(ValidationError)` |

- `chdir(tmp_path)` keeps the repo's `config.toml` and any `.env` out of the test.
- `monkeypatch.delenv(<name>, raising=False)` every variable the test is about, in
  case the developer's shell sets it.

```python
def test_app_settings_env_var_overrides_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_toml_path = tmp_path / "config.toml"
    config_toml_path.write_text('app_name = "From Toml"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_NAME", "From Env")

    loaded_app_settings = AppSettings()

    assert loaded_app_settings.app_name == "From Env"
```

## §9 Logging and middleware

| Situation                         | Pattern |
| --------------------------------- | ------- |
| A log event is a requirement (token counts per LLM call) | Wrap the act in `structlog.testing.capture_logs()`; find the event by name and assert its keys |
| Request-id middleware             | A route test on any route: the response carries the header, and a header sent in is echoed back |
| Not tested                        | Log formatting, renderer output, Logfire export |

`capture_logs()` can't see a logger cached before it was entered. Don't turn on
`cache_logger_on_first_use` when `ENVIRONMENT` is `TEST`.

```python
async def test_complete_logs_token_counts(
    llm_service: LlmService, openai_handler_stub: HttpHandlerStub
) -> None:
    openai_payload = build_openai_chat_completion_payload(prompt_tokens=12, completion_tokens=5)
    openai_handler_stub.handle_responses.append(httpx.Response(200, json=openai_payload))
    llm_completion_input = build_llm_completion_input()

    with structlog.testing.capture_logs() as captured_log_events:
        await llm_service.complete(llm_completion_input)

    completion_log_events = [
        log_event
        for log_event in captured_log_events
        if log_event["event"] == "llm_completion_finished"
    ]
    assert len(completion_log_events) == 1
    assert completion_log_events[0]["input_tokens"] == 12
    assert completion_log_events[0]["output_tokens"] == 5
```

## §10 Migrations

Tests live in `tests/migrations/test_revisions.py`. File checks run in the default
suite. The stairway test is marked `migration` and runs in its own invocation
(`uv run pytest -m migration`), because rebuilding the schema mid-run invalidates
asyncpg's cached type ids for any database tests that follow. CI runs it in the
migrations job beside the drift check.

| Situation                    | Pattern |
| ---------------------------- | ------- |
| One head                     | `ScriptDirectory.get_heads()` returns one entry. Two revisions with the same `down_revision` fail |
| Every up has a down          | Every `migrations/sql/*/*.up.sql` has a `.down.sql` sibling |
| Downgrade reverses upgrade   | Stairway: starting from empty, for each revision run upgrade, downgrade `-1`, upgrade. A down file that forgets `DROP TYPE` fails on the second upgrade |
| Orm matches the schema       | Not pytest. CI's `alembic check` drift job covers it |

```python
# tests/migrations/conftest.py
@pytest.fixture
async def empty_test_database(db_engine: AsyncEngine) -> None:
    async with db_engine.begin() as db_connection:
        await db_connection.execute(text("DROP SCHEMA public CASCADE"))
        await db_connection.execute(text("CREATE SCHEMA public"))
```

```python
# tests/migrations/test_revisions.py
def test_revision_chain_has_single_head(pytestconfig: pytest.Config) -> None:
    alembic_config = Config(pytestconfig.rootpath / "alembic.ini")
    script_directory = ScriptDirectory.from_config(alembic_config)

    revision_heads = script_directory.get_heads()

    assert len(revision_heads) == 1


def test_every_up_sql_file_has_down_sql_file(pytestconfig: pytest.Config) -> None:
    sql_root_path = pytestconfig.rootpath / "migrations" / "sql"

    up_sql_paths = sorted(sql_root_path.glob("*/*.up.sql"))

    missing_down_sql_paths: list[Path] = []
    for up_sql_path in up_sql_paths:
        down_sql_name = up_sql_path.name.replace(".up.sql", ".down.sql")
        if not up_sql_path.with_name(down_sql_name).exists():
            missing_down_sql_paths.append(up_sql_path)
    assert missing_down_sql_paths == []


@pytest.mark.migration
@pytest.mark.usefixtures("empty_test_database")
def test_every_revision_downgrades_and_upgrades_again(pytestconfig: pytest.Config) -> None:
    alembic_config = Config(pytestconfig.rootpath / "alembic.ini")
    script_directory = ScriptDirectory.from_config(alembic_config)
    revisions_head_first = list(script_directory.walk_revisions())

    for revision in reversed(revisions_head_first):
        for alembic_arguments in (
            ["upgrade", revision.revision],
            ["downgrade", "-1"],
            ["upgrade", revision.revision],
        ):
            subprocess.run(
                [sys.executable, "-m", "alembic", *alembic_arguments],
                cwd=pytestconfig.rootpath,
                check=True,
            )
```

The stairway test has no `assert`: `check=True` raises on the first failing command.

## §11 LangGraph workflows (provisional)

`fastapi-structure.md` has no graph conventions yet. Revisit this section when the
first graph lands.

| Situation                   | Pattern |
| --------------------------- | ------- |
| Node                        | A node is a function of state. Test it like a service: stubs in, assert the returned state update |
| Conditional edge            | Call the routing function with a hand-built state and assert the next node's name |
| Whole run                   | Compile with `InMemorySaver` and stubs whose `<method>_results` are scripted per pass. `ainvoke`, then assert the final state and the stub's call count |
| Loop bound                  | The stub never meets the exit condition. Assert the graph stops at the settings limit, not at a recursion error |
| Human review interrupt      | `ainvoke` to the interrupt, then assert `aget_state(...).next` names the review node |
| Resume after review         | From the interrupt, `ainvoke(Command(resume=...))` and assert where the graph went: publish on approval, back to rewrite on rejection |

```python
async def test_post_review_graph_publishes_after_approval() -> None:
    llm_service_stub = LlmServiceStub()
    post_review_graph = build_post_review_graph(
        llm_service=llm_service_stub, checkpointer=InMemorySaver()
    )
    graph_run_config = {"configurable": {"thread_id": "test-thread"}}
    await post_review_graph.ainvoke({"draft_text": "Sourdough is alive."}, graph_run_config)

    await post_review_graph.ainvoke(Command(resume={"approved": True}), graph_run_config)

    graph_state_snapshot = await post_review_graph.aget_state(graph_run_config)
    assert graph_state_snapshot.values["review_status"] == ReviewStatusType.PUBLISHED
```

## §12 Live LLM tests

Mark these `@pytest.mark.live_llm`. They're deselected by default and never run in
CI.

- Read the key from `LIVE_OPENAI_API_KEY`. The root fixture overwrites
  `OPENAI_API_KEY` with a fake. If the variable is missing, call `pytest.skip`.
- Test the contract only: the real response parses into our `Result`, the content
  isn't empty, token counts are positive.
- Never assert on wording. A human judges prompt quality, not pytest.
- Keep it to one or two tests, since they cost money.

## Running

```bash
uv run pytest                                    # all but live_llm and migration
uv run pytest tests/libs/users                   # one folder
uv run pytest tests/api/users/test_router.py::test_get_me_signed_out_returns_401
uv run pytest -k duplicate_email                 # names containing a substring
uv run pytest -x --lf                            # rerun last failures, stop at the first
uv run pytest -m migration                       # stairway migration test
LIVE_OPENAI_API_KEY=... uv run pytest -m live_llm  # real LLM calls
```
