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

Examples leave out imports, and the domains in them are invented, so a pattern here
never goes stale when the app changes: a `weather` lib whose `WeatherService` calls a
third-party forecast API, and a `forecast_digest` lib whose `ForecastDigestService`
composes it. They stand in for whatever the real domains are. Only infrastructure
names are real — the fixtures, the folder layout, `AuthUserDep`, `BaseOrm`, and the
markers in `pyproject.toml`.

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
│   └── weather.py           # WeatherServiceStub
├── payloads/
│   └── weather_api.py       # third-party response bodies, as builder functions
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
  - a lib with a `services/` package → one test module per service, flat:
    `libs/auth/services/oauth_state_service.py` →
    `tests/libs/auth/test_oauth_state_service.py`
  - `apps/api/domains/<domain>/<module>.py` → `tests/api/<domain>/test_<module>.py`
  - `apps/api/<module>.py` → `tests/api/test_<module>.py`
  - A second app gets `tests/<app_name>/`.
- Filenames are short, like source filenames: `tests/api/users/test_router.py`, never
  `test_users_router.py`. `--import-mode=importlib` allows the same basename in more
  than one folder.
- No `__init__.py` anywhere under `tests/`.
- A test module never imports from another test module or from a `conftest.py`.
  Shared code lives in `factories/`, `stubs/`, or `payloads/`, imported as
  `from tests.stubs.weather import WeatherServiceStub`.
- `factories/` and `stubs/` have one module per lib domain, named after the lib
  package. `tests/stubs/weather.py` stubs `libs/weather/`. `payloads/` has one module per
  third-party provider.

## What to write for each source file

| Source                               | Test file                              | Required cases |
| ------------------------------------ | -------------------------------------- | -------------- |
| `libs/<d>/services.py`, or each module in `libs/<d>/services/` | `tests/libs/<d>/test_services.py`, or `test_<service>.py` | For each public method: happy path, each branch, each exception it raises, each collaborator failure it handles. With a database, also persisted state, not found, constraint violations, related rows loaded (§2, §3) |
| `libs/<d>/prompts.py`                | `tests/libs/<d>/test_prompts.py`       | Each builder: the arguments appear in the output (§1) |
| `libs/<d>/utils/*.py`, `libs/core/utils/*.py` | `tests/libs/<d>/test_<utils>.py` | Every branch of every static method (§1, §2). A `Utils` class whose only output is a wall-clock measurement, like `DateTimeUtils`, gets no file: its effect is asserted through the service |
| `libs/<d>/inputs.py`, `results.py`   | `tests/libs/<d>/test_inputs.py`, `test_results.py` | Only models with a validator or declared constraint: accepted and rejected values (§1) |
| `libs/<d>/states.py`                 | `tests/libs/<d>/test_states.py`        | Only a method that does more than group stored fields; otherwise the graph and service tests cover it |
| Class with an enum dispatch map      | That class's test file                 | Every enum member has a handler (§1) |
| `apps/api/domains/<d>/router.py`     | `tests/api/<d>/test_router.py`         | For each route: happy path, 422 per declared constraint, each exception the service raises, 401 if protected, persisted state for writes (§6) |
| `apps/api/domains/<d>/dtos.py`, `apps/api/core/dtos.py` | None, unless a mapper has logic | Route tests cover plain field copying |
| `apps/api/domains/<d>/dependencies.py` | None                                 | Route tests run the real factories |
| `apps/api/core/dependencies.py`      | `tests/api/core/test_dependencies.py`  | Session discards writes, transaction commits and rolls back, auth guard cases (§7) |
| `apps/api/core/config.py`            | `tests/api/core/test_config.py`        | TOML beats default, env beats TOML, missing secret fails (§8) |
| `apps/api/core/exception_handlers.py` | `tests/api/core/test_exception_handlers.py` | Each standard exception maps to its status; a lib exception gets its parent's; unhandled errors return 500 without internals (§7) |
| `libs/core/exceptions.py`, `libs/<d>/exceptions.py` | None                   | The app factory tests and the service tests that raise them cover these |
| `apps/api/lifespan.py`               | `tests/api/test_lifespan.py`           | Resources created at startup and closed at shutdown (§7) |
| `libs/<d>/tasks.py`                  | `tests/libs/<d>/test_tasks.py`         | Call the task directly with the `db_session_factory` and `redis_client` fixtures, and assert the persisted effect. Don't assert a background task ran from a route test: the task opens a second session on the shared test connection, and the harness loses that write |
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
  - `test_build_digest_unknown_region_type_returns_422`
- No test classes. Group tests by file and by the `<unit>` prefix.
- A fixture is a noun, named exactly like the production object it stands for:
  `db_session`, `redis_client`, `app_settings`, `fastapi_app`, `api_client`. Never a
  `test_`, `get_`, or `mock_` prefix.
- `python-naming.md` applies in full, so write `create_user_response`, not
  `response`, and `user_query_result`, not `result`.
- A stub class is named `<Class>Stub`, e.g. `WeatherServiceStub`.
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
  `unittest.mock`. It works inside a plain dict or JSON comparison; a Pydantic model
  rejects it at validation, so assert those fields individually instead.
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
| A `Utils` class                     | Nothing. It is pure, so call the real one                     |
| Anything reachable only by patching | Nothing. Report it: the code has a hidden dependency to fix   |

A `Utils` class is never stubbed. Its methods are static and pure — same inputs, same
outputs, no I/O and no clock — so the reason to stub a collaborator doesn't apply, and
faking one would mean patching. Its own test module covers every branch; a service
test calls the real one and asserts the wiring, not the arithmetic, keeping its
expected values simple enough to read at a glance.

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
# tests/stubs/weather.py
class WeatherServiceStub(WeatherService):
    def __init__(self) -> None:
        self.fetch_forecast_inputs: list[FetchForecastInput] = []
        self.fetch_forecast_result = build_fetch_forecast_result()
        self.fetch_forecast_error: Exception | None = None

    async def fetch_forecast(self, fetch_forecast_input: FetchForecastInput) -> FetchForecastResult:
        self.fetch_forecast_inputs.append(fetch_forecast_input)
        if self.fetch_forecast_error is not None:
            raise self.fetch_forecast_error
        return self.fetch_forecast_result
```

### Test data

Test data comes from `tests/factories/<domain>.py`, one module per lib domain:

- `build_<model>(...)` returns an `Input`, a `Result`, an unsaved `Orm`, or a graph
  state model. Sync.
- `insert_<entity>_row(db_session, ...)` adds and flushes an `Orm` and returns it.
  Async. It bypasses services, so a test of one service never depends on another
  service working.
- Every parameter is keyword-only with a valid default, so a test passes only the
  values it asserts on. Unique columns default to a fresh value.
- Datetimes are aware UTC literals: `datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)`. A
  naive datetime fails at flush.
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
    user_record = UserOrm(email=email or _build_unique_email(), display_name=display_name)
    db_session.add(user_record)
    await db_session.flush()
    return user_record


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
the database and Redis in step 6, `signed_in_user` in step 9).

`tests/conftest.py` holds infrastructure every app and lib uses: the
`environment_variables` fixture that points the suite at `pb_test` and Redis index 15,
`app_settings`, `db_engine`, `db_connection`, `db_session_factory`, `db_session` and
`redis_client`. `tests/api/conftest.py` holds the app fixtures — `fastapi_app`,
`api_client` and `signed_in_user` — so only tests under `tests/api/` can see them, and
lib tests can't reach the app. Read those two files rather than copying them from here.

What these fixtures guarantee:

- **Real migrations.** `db_engine` wipes the schema and runs the real migrations once
  per session. Tests run against the schema the migrations build, never
  `BaseOrm.metadata.create_all()`, so a broken `.up.sql` fails the suite.
- **Rollback per test.** Each test gets one connection inside an outer transaction
  that's rolled back at teardown. `join_transaction_mode="create_savepoint"` turns
  every session's `begin()` and `commit()` into a savepoint, so services and routes
  that commit still leave nothing behind. The factory comes from
  `create_db_session_factory()`, so every other session option and the soft-delete
  rule match production. Only `join_transaction_mode` is added.
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
# tests/libs/forecast_digest/test_prompts.py
def test_build_user_prompt_includes_station_name() -> None:
    user_prompt = ForecastDigestPrompt.build_user_prompt(
        station_name="pier-17",
        region_type=RegionType.COASTAL,
    )

    assert "pier-17" in user_prompt
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
# tests/libs/forecast_digest/test_services.py
async def test_build_digest_returns_content_and_character_count() -> None:
    weather_service_stub = WeatherServiceStub()
    weather_service_stub.fetch_forecast_result = build_fetch_forecast_result(summary="Rain all day")
    forecast_digest_service = ForecastDigestService(weather_service=weather_service_stub)
    build_digest_input = build_build_digest_input()

    build_digest_result = await forecast_digest_service.build_digest(build_digest_input)

    assert build_digest_result == BuildDigestResult(
        content="Rain all day",
        character_count=12,
    )
```

## §3 Database tests

These are service tests that take the `db_session` fixture. They hit real Postgres,
rolled back after each test.

| Situation                         | Pattern |
| --------------------------------- | ------- |
| Create                            | Call, then `select()` the row back and assert on it. The returned `Result` alone proves nothing about persistence |
| Primary key and server defaults   | Assert `id` and `identity` are set and `created_at is not None`. Never assert an exact timestamp |
| Soft delete                       | Call, then assert the ORM `select()` no longer finds the row and a raw `text()` select still does, with `deleted_at` and `deleted_by_id` set |
| Audit columns                     | Assert `created_by_id` / `updated_by_id` equal the `AuthUser` the test passed in |
| Read, found                       | `insert_*_row`, call, compare the whole `Result` built from the row's values |
| Read, not found                   | Call with a key that was never inserted and `pytest.raises(NotFoundException)` |
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
    user_record = await db_session.scalar(user_query)
    assert user_record is not None
    assert user_record.email == "ada@example.com"
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

`tests/stubs/http.py` holds `HttpHandlerStub`, which records every request, raises
`handle_error` when set, and pops the next queued response.

```python
# tests/libs/weather/conftest.py
@pytest.fixture
def weather_api_handler_stub() -> HttpHandlerStub:
    return HttpHandlerStub()


@pytest.fixture
async def weather_service(
    weather_api_handler_stub: HttpHandlerStub,
) -> AsyncIterator[WeatherService]:
    weather_api_transport = httpx.MockTransport(weather_api_handler_stub.handle)
    async with httpx.AsyncClient(transport=weather_api_transport) as weather_http_client:
        weather_settings = WeatherSettings(station_name="test-station")
        yield WeatherService(
            http_client=weather_http_client, weather_settings=weather_settings
        )
```

```python
# tests/libs/weather/test_services.py
async def test_fetch_forecast_sends_station_from_settings_and_returns_summary(
    weather_service: WeatherService, weather_api_handler_stub: HttpHandlerStub
) -> None:
    weather_api_payload = build_weather_api_forecast_payload(
        summary="Rain all day", high_celsius=14
    )
    weather_api_handler_stub.handle_responses.append(
        httpx.Response(200, json=weather_api_payload)
    )
    fetch_forecast_input = build_fetch_forecast_input()

    fetch_forecast_result = await weather_service.fetch_forecast(fetch_forecast_input)

    sent_request_url = weather_api_handler_stub.handle_requests[0].url
    assert sent_request_url.params["station"] == "test-station"
    assert fetch_forecast_result == FetchForecastResult(
        summary="Rain all day", high_celsius=14
    )
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
# tests/libs/auth/test_auth_session_service.py
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
`get_weather_service` or the Google token verifier's factory), never the service the
route calls. That way the domain's `dependencies.py` still runs for real. If no such
dependency exists because the domain factory builds a third-party client inline,
report it and propose splitting it out.

Put the override in the domain's `conftest.py` as an `autouse` fixture:

```python
# tests/api/forecast_digest/conftest.py
@pytest.fixture(autouse=True)
def weather_service_stub(fastapi_app: FastAPI) -> WeatherServiceStub:
    weather_service_stub = WeatherServiceStub()
    fastapi_app.dependency_overrides[get_weather_service] = lambda: weather_service_stub
    return weather_service_stub
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
    user_record = await insert_user_row(db_session)
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=app_settings.auth
    )
    session_id = await auth_session_service.create_session(user_id=user_record.id)
    api_client.cookies.set("sid", session_id)
    return user_record
```

| Situation                     | Pattern |
| ----------------------------- | ------- |
| Happy path                    | Send raw JSON; assert the status and the whole `response.json()` |
| Wire format                   | Request bodies and expected responses are dict literals, never `Dto(...).model_dump()`. The test is what pins the JSON contract |
| Validation → 422              | Parametrize one missing required field plus one case per constraint the DTO declares. Assert the status and `detail[0]["loc"]`, never the message |
| Exception → status            | Set up the real condition (insert the duplicate row), or set the stub's `<method>_error`. Assert the status and the `{"detail": ...}` body |
| Create (`POST`)               | Select the row by the returned `identity` and assert its columns. The body is `{"identity": "<uuid>"}` |
| Malformed identity → 422      | One test per route with an identity path parameter: a non-UUID value returns 422 |
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
# tests/api/forecast_digest/test_router.py
@pytest.mark.usefixtures("signed_in_user")
async def test_build_digest_returns_forecast_digest_response(
    api_client: AsyncClient, weather_service_stub: WeatherServiceStub
) -> None:
    weather_service_stub.fetch_forecast_result = build_fetch_forecast_result(
        summary="Rain all day"
    )

    build_digest_response = await api_client.post(
        "/forecast-digest",
        json={"region_type": "COASTAL", "station_name": "pier-17"},
    )

    assert build_digest_response.status_code == 200
    assert build_digest_response.json() == {
        "content": "Rain all day",
        "character_count": 12,
    }


@pytest.mark.usefixtures("signed_in_user")
@pytest.mark.parametrize(
    ("request_body", "expected_error_location"),
    [
        pytest.param(
            {"station_name": "pier-17"},
            ["body", "region_type"],
            id="missing_region_type",
        ),
        pytest.param(
            {"region_type": "LUNAR", "station_name": "pier-17"},
            ["body", "region_type"],
            id="unknown_region_type",
        ),
    ],
)
async def test_build_digest_invalid_body_returns_422(
    api_client: AsyncClient,
    request_body: dict[str, str],
    expected_error_location: list[str],
) -> None:
    build_digest_response = await api_client.post("/forecast-digest", json=request_body)

    response_body = build_digest_response.json()
    assert build_digest_response.status_code == 422
    assert response_body["detail"][0]["loc"] == expected_error_location


@pytest.mark.usefixtures("signed_in_user")
async def test_build_digest_weather_unavailable_returns_503(
    api_client: AsyncClient, weather_service_stub: WeatherServiceStub
) -> None:
    weather_service_stub.fetch_forecast_error = WeatherUnavailableException()

    build_digest_response = await api_client.post(
        "/forecast-digest",
        json={"region_type": "COASTAL", "station_name": "pier-17"},
    )

    assert build_digest_response.status_code == 503


async def test_build_digest_signed_out_returns_401(api_client: AsyncClient) -> None:
    build_digest_response = await api_client.post(
        "/forecast-digest",
        json={"region_type": "COASTAL", "station_name": "pier-17"},
    )

    assert build_digest_response.status_code == 401
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
    inserted_user_record = await db_session.scalar(user_query)
    assert insert_user_response.status_code == 200
    assert inserted_user_record is None
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
| A log event is a requirement (token counts per LLM call, see §12) | Wrap the act in `structlog.testing.capture_logs()`; find the event by name and assert its keys |
| Request-id middleware             | A route test on any route: the response carries the header, and a header sent in is echoed back |
| Not tested                        | Log formatting, renderer output, Logfire export |

`capture_logs()` can't see a logger cached before it was entered. Don't turn on
`cache_logger_on_first_use` when `ENVIRONMENT` is `TEST`.

```python
async def test_fetch_forecast_logs_station_and_high(
    weather_service: WeatherService, weather_api_handler_stub: HttpHandlerStub
) -> None:
    weather_api_payload = build_weather_api_forecast_payload(high_celsius=14)
    weather_api_handler_stub.handle_responses.append(
        httpx.Response(200, json=weather_api_payload)
    )
    fetch_forecast_input = build_fetch_forecast_input()

    with structlog.testing.capture_logs() as captured_log_events:
        await weather_service.fetch_forecast(fetch_forecast_input)

    forecast_log_events = [
        log_event
        for log_event in captured_log_events
        if log_event["event"] == "forecast_fetched"
    ]
    assert len(forecast_log_events) == 1
    assert forecast_log_events[0]["station_name"] == "test-station"
    assert forecast_log_events[0]["high_celsius"] == 14
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

`tests/migrations/test_revisions.py` holds all three, with the `empty_test_database`
fixture in its `conftest.py`.

The stairway test has no `assert`: `check=True` raises on the first failing command.

## §11 LangGraph workflows

`fastapi-structure.md` › LangGraph workflows says where nodes, states and graphs live.
A routing function is private and covered by whole-run tests, never called directly.
A node that calls `interrupt()` can't run outside a graph, so it is covered the same
way.

| Situation                   | Pattern |
| --------------------------- | ------- |
| Node                        | Take it from `get_node(<Domain>NodeType.X)` and call it with a state: stubs in, assert the returned state update |
| Every node type has a node  | Parametrize over `list(<Domain>NodeType)` and assert `get_node` returns one for each |
| A node that interrupts      | Can't run outside a graph. Cover it through the whole-run tests |
| Whole run                   | Compile with `InMemorySaver` and stubs whose `<method>_results` are scripted per pass. `ainvoke`, then assert the final state and the stub's call count |
| Loop bound                  | The stub never meets the exit condition. Assert the graph stops at the settings limit, not at a recursion error |
| Human review interrupt      | `ainvoke` to the interrupt, then assert `aget_state(...).interrupts[0].value` carries the paused payload |
| Resume after review         | From the interrupt, `ainvoke(Command(resume=...))` and assert where the graph went: publish on approval, back to rewrite on rejection |

```python
async def test_forecast_digest_graph_publishes_after_approval() -> None:
    weather_service_stub = WeatherServiceStub()
    forecast_digest_graph = build_forecast_digest_graph(
        weather_service=weather_service_stub, checkpointer=InMemorySaver()
    )
    graph_run_config = {"configurable": {"thread_id": "test-thread"}}
    await forecast_digest_graph.ainvoke({"draft_text": "Rain all day"}, graph_run_config)

    await forecast_digest_graph.ainvoke(Command(resume={"approved": True}), graph_run_config)

    graph_state_snapshot = await forecast_digest_graph.aget_state(graph_run_config)
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
uv run pytest tests/api/users/test_router.py::test_find_signed_in_user_signed_out_returns_401
uv run pytest -k duplicate_email                 # names containing a substring
uv run pytest -x --lf                            # rerun last failures, stop at the first
uv run pytest -m migration                       # stairway migration test
LIVE_OPENAI_API_KEY=... uv run pytest -m live_llm  # real LLM calls
```
