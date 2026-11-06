---
paths:
  - "backend/tests/**/*.py"
---

# Tests

pytest, run from `backend/`. A test goes through the same entry points production
uses: a service built with its `__init__`, a route called over HTTP, and real Postgres
and Redis. Nothing is patched.

Examples leave out imports. `weather`/`WeatherService` and
`forecast_digest`/`ForecastDigestService` are invented stand-ins for real domains;
fixture names, folders, `AuthUserDep`, `BaseOrm` and the markers are real.

Tools: pytest, pytest-asyncio, httpx (`ASGITransport` to call the app,
`MockTransport` to fake third-party HTTP), `structlog.testing`, and real Postgres and
Redis from docker compose, never SQLite or fakeredis. `pytest-mock`, `respx`,
`factory_boy`, `freezegun`, `pytest-env` and `asgi-lifespan` each have an in-house
pattern below, so none is a reason to add a dependency (CLAUDE.md › Non-obvious stack
choices).

## Layout

`backend/tests/` mirrors the source:

- `libs/<d>/<module>.py` → `tests/libs/<d>/test_<module>.py`. A `services/` package
  gets one flat module per service (`libs/auth/services/oauth_state_service.py` →
  `tests/libs/auth/test_oauth_state_service.py`). Deeper packages keep their folders
  (`libs/<d>/graphs/<variant>/prompts/<p>.py` →
  `tests/libs/<d>/graphs/<variant>/prompts/test_<p>.py`).
- `apps/api/domains/<d>/<module>.py` → `tests/api/<d>/test_<module>.py`;
  `apps/api/<module>.py` → `tests/api/test_<module>.py`. A second app gets
  `tests/<app_name>/`.
- Shared helpers have one module per lib domain, named after the lib package:
  `tests/factories/<d>.py` and `tests/stubs/<d>.py`. Third-party response bodies go in
  `tests/payloads/<provider>.py`. Import them as
  `from tests.stubs.weather import WeatherServiceStub`. A test module never imports
  from another test module or from a `conftest.py`.
- Filenames are short, like source filenames: `tests/api/users/test_router.py`, never
  `test_users_router.py`. No `__init__.py` anywhere under `tests/`.

## What to write for each source file

| Source | Test file | Required cases |
| ------ | --------- | -------------- |
| `libs/<d>/services.py`, or each module in `services/` | `test_services.py`, or `test_<service>.py` | For each public method: happy path, each branch, each exception it raises, each collaborator failure it handles. With a database, also §3 |
| `prompts.py`, or each module in a `prompts/` package | The mirrored module | Each builder: the inputs land in the prompt they belong in (§1) |
| A graph variant's `<variant>_<what>_output_format.py` | The mirrored module | `normalize_output`: each fix it makes and what it leaves alone. `validate_output`: each problem on its own, and a valid document with none (§1) |
| `utils/*.py` | `test_<utils>.py` | Every branch of every static method. A `Utils` that builds queries runs them against the test DB (§3); compare compiled SQL only for what a result can't show, such as a dropped `ORDER BY`. A `Utils` whose only output is a wall-clock measurement gets no file |
| `libs/database/pagination_config.py` | `tests/libs/database/test_pagination_config.py` | One parametrized test over every (pagination config, input class) pair: each `filters` key is a field of the input class |
| `inputs.py`, `results.py`, `settings.py` | The mirrored module | Only models with a validator or declared constraint: accepted and rejected values (§1) |
| `states.py` | `test_states.py` | Only a method that does more than group stored fields |
| Class with an enum dispatch map | That class's test file | Every enum member has a handler (§1) |
| `libs/<d>/after_response_tasks.py` | The mirrored module | Call the task directly with the fixtures it takes (`db_session_factory`, `redis_client`), and assert the persisted effect |
| `apps/api/domains/<d>/router.py` | `tests/api/<d>/test_router.py` | For each route: happy path, 422 per declared constraint, each exception the service raises, 401 if protected, 403 if a signed-in fixture lacks its permission, persisted state for writes (§6) |
| Middleware | `tests/api/test_<module>.py` | Observable effect on a real route (§9) |
| `apps/api/core/*.py`, `app_factory.py`, `lifespan.py`, `migrations/` | The existing test file | Extend it (§7, §8, §10) |

No test file for: a domain's `dtos.py` (unless a mapper has logic, §1), a domain's
`dependencies.py`, `exceptions.py`, `libs/database/orm/*.py`, `constants.py` (beyond
the pagination config guard above). Route, service and app-factory tests and CI's
drift check cover them.

## Conventions for every test

### Naming

- A test function is named `test_<unit>_<condition>_<outcome>`. Leave out
  `<condition>` for the default path. `<unit>` is the service method or route handler
  name.
  - `test_create_user_returns_created_user`
  - `test_create_user_email_taken_raises_user_email_taken_exception`
  - `test_build_digest_unknown_region_type_returns_422`
- When a full exception class name would push a test name past the line limit,
  shorten `<outcome>` to the exception's distinguishing words:
  `..._raises_persona_private_exception`, not the whole class name.
- No test classes. Group tests by file and by the `<unit>` prefix.
- A fixture is a noun, named exactly like the production object it stands for:
  `db_session`, `redis_client`, `app_settings`, `fastapi_app`, `api_client`. Never a
  `test_`, `get_`, or `mock_` prefix.
- `python-naming.md` applies in full, so write `create_user_response`, not
  `response`, and `user_query_result`, not `result`.
- A named expected value is `expected_<thing>`.

### Shape of a test

Arrange, act, assert: three blocks separated by blank lines, with no `# Arrange`
comments. Tests get no step comments either (`python-naming.md` › Other conventions).
The act block is the single call under test. If the assert block needs a value pulled
out of the result first, that line starts the assert block.

Test one behaviour per test. Several asserts are fine when they describe the same
outcome; a second action belongs in a second test.

Write expected values as literals in the test, never recomputed with the code's own
logic: `character_count=19`, not `len(content)`. The no-loose-literals rule covers
`libs/` and `apps/`, not tests. Test data should be visible where it's asserted.
Expected values come from the intended behaviour; never run the code and copy its
output into an assertion.

When behaviour depends on a setting, build the settings model in the test with a
non-default value, e.g. `WeatherSettings(max_retries=2)`. Never rely on the default.

### Assertions

- Compare whole objects: `assert create_user_result == CreateUserResult(...)` and
  `assert create_user_response.json() == {...}`. Whole-object equality catches added,
  missing and leaked fields. Field-by-field asserts don't.
- A test of ordering, search or paging may compare the list of one identifying field,
  as long as one test per method compares the whole Result.
- If the test can't know a value (like a server timestamp), take it from the seeded
  row. Failing that, use `unittest.mock.ANY`. `ANY` is the only import allowed from
  `unittest.mock`. It works inside a plain dict or JSON comparison; a Pydantic model
  rejects it at validation, so assert those fields individually instead.
- Assert exceptions with `with pytest.raises(UserEmailTakenException):`. Add `match=`
  only when the message is part of the contract, such as user-facing text. When the
  behaviour under test is that one message lists several problems, check each problem
  with `in`, never the exact full string.
- Don't assert on log wording, exception messages, or FastAPI's validation `msg`. A log
  event's name and keys aren't wording (§9).

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
- A third-party override that several domains' route tests need, such as the LLM
  stub, is an opt-in fixture in `tests/api/conftest.py`, never autouse there: an
  app-level autouse fixture pulls in whichever `fastapi_app` a domain overrides. A
  module opts in with `pytestmark = pytest.mark.usefixtures("llm_service_stub")`, or a
  test requests it by name to configure it.
- When a fixture is only needed for its side effect, request it with
  `@pytest.mark.usefixtures("signed_in_user")`, not as an unused argument.
- Test data is not a fixture. Build any value a test asserts on inside that test,
  with a `factories/` function. The shared data fixtures are the signed-in ones (§6),
  because signing in is setup, not the thing under test.

### Async

- Never use `asyncio.run()`, `loop.run_until_complete()`, `time.sleep()`, or
  `asyncio.sleep()` in a test. If a test has to wait for something, it isn't
  controlling that thing. `asyncio.sleep(0)` is allowed: it only lets other tasks run
  and never waits on the clock. The one other exception is the event loop lag
  monitor's own test, which may block the loop and sleep, because lag only exists when
  the loop is really blocked.
- A test that must act while a job is mid-step uses the stub's blocking hooks, never a
  sleep: set `<method>_is_blocked`, wait on `<method>_started_event` to know the job
  got there, then set `<method>_unblock_event` to let it carry on.
- A test that starts a background job waits for it with
  `await background_job_service.drain(...)` before asserting or touching the database
  again. The job and the test share one test connection, which can't serve two
  operations at once. Service tests build a real `BackgroundJobService`; route tests
  get the app's through the `background_job_service` fixture.

### Test doubles

Use stubs, never mocks.

| Collaborator                        | Double                                                        |
| ----------------------------------- | ------------------------------------------------------------- |
| One of our services                 | Hand-written `<Class>Stub` in `tests/stubs/<domain>.py`       |
| A `Prompt` handed to a generic node or service | Hand-written `<Name>PromptStub` returning a fixed `BuildPromptResult`, placed and named like a service stub |
| Third-party HTTP API                | The real SDK client over `httpx.MockTransport` (§4)           |
| Postgres, Redis                     | The real thing                                                |
| A `Utils` class                     | Nothing. It is pure, so call the real one                     |
| Anything reachable only by patching | Nothing. Report it: the code has a hidden dependency to fix   |

A service test calls the real `Utils` and asserts the wiring, not the arithmetic,
keeping its expected values simple enough to read at a glance.

- `unittest.mock.patch`, `MagicMock`, `AsyncMock`, and `monkeypatch.setattr` are
  banned. Needing one means the code should take that dependency through `__init__`
  or a dependency factory.
- Use `monkeypatch` only for environment variables (`setenv`, `delenv`) and
  `chdir`.

How to write a stub (shape: `tests/stubs/google_auth.py`; `tests/stubs/llm.py` for
`_results` and the blocking hooks):

- Subclass the real class and override only the public methods tests need.
- Never call `super().__init__()`. A method that isn't overridden then fails loudly
  instead of doing real work.
- A stub may wrap a real instance of the class and pass calls through to it, when the
  test needs the real effect plus a hook, such as an event to wait on. It then passes
  through every method its consumer calls, since an un-`__init__`'d subclass has no
  state of its own.
- Name the stub's attributes `<method>_` plus what they hold:
  - `<method>_inputs`: every input received, in order
  - `<method>_result`: the value to return
  - `<method>_results`: values popped in order, for when calls must differ (such as a
    rewrite loop). When it's set it wins over `<method>_result`, and running out
    raises, so a test that makes more calls than it scripted fails. An exception in
    the list is raised instead of returned, for "fails, then succeeds"
  - `<method>_error`: an exception to raise instead
  - `<method>_<collaborator>`: a real collaborator the method hands its work to, set
    by the test, so a route test can assert what was stored in Redis or the database
    while the outside call stays stubbed

### Test data

Test data comes from `tests/factories/<domain>.py`, one module per lib domain (shape:
`tests/factories/users.py`):

- `build_<model>(...)` returns an `Input`, a `Result`, an unsaved `Orm`, or a graph
  state model. Sync.
- `insert_<entity>_row(db_session, ...)` adds and flushes an `Orm` and returns it.
  Async. It bypasses services, so a test of one service never depends on another
  service working.
- `find_<entity>_row(db_session)` returns a row the migrations seed, such as the
  system user. Async.
- Every parameter is keyword-only with a valid default, so a test passes only the
  values it asserts on. Unique columns default to a fresh value.
- Write out keyword parameters, never `**overrides`, so a typo fails.
- Datetimes are aware UTC literals: `datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)`.
- A test that needs an exact `created_at` order passes `created_at` to the
  `insert_*_row` factory, since every row in a test's transaction otherwise gets the
  same timestamp. A factory leaves the column unset when it's `None`, so the default
  fills it in.
- To move a row to the next state partway through a test, set the column on the row
  the test inserted and flush. Never reach that state through another service.
- A test of exception-hierarchy behaviour, such as most-specific matching, may declare
  a throwaway `<What>Exception` subclass in its own module.

### Determinism

- Tests pass in any order and on their own. No module-level mutable state.
- No network except local Postgres and Redis.
- No wall clock in assertions. Assert that a TTL is within bounds, that a timestamp is
  not `None`, or that a stored time equals the database's now read on `db_session`,
  which is fixed inside the test's transaction (`database.md` › Timestamps). A stored
  time that code compares with now, such as a lease expiry, is a literal far on the
  side the test needs, `datetime(2026, 1, 2, tzinfo=UTC)` for the past and a 2099 date
  for the future, never an offset from now.
- No randomness, apart from the unique-value defaults in factories.

### What not to test

- Framework behaviour: Pydantic coercing types, `frozen=True` freezing, FastAPI
  rejecting a missing body. Test only constraints this codebase declares.
- Setting defaults and constant values.
- `_private` methods directly. Test them through the public method that uses them.
  The one exception is an enum dispatch map (§1).
- Dependency factories, `Annotated` aliases, and `to_input()` / `from_result()` that
  only copy fields: route tests run them.

## Configuration

`[tool.pytest]` in `pyproject.toml` (pytest 9's native table, never
`[tool.pytest.ini_options]`) sets what every test lives with:

- `filterwarnings = ["error"]`: any warning fails, including the `RuntimeWarning` from
  a forgotten `await`. A third-party warning we can't fix gets a specific
  `"ignore:<message>:<Category>"` line with a comment saying why, never a blanket
  ignore.
- `strict = true`: an unregistered marker, a mistyped config key, or a duplicate
  parametrize id fails the run.
- `asyncio_mode = "auto"` with one session-wide event loop: write `async def test_...`
  without `@pytest.mark.asyncio`.
- The default `-m` expression deselects `live_llm` and `migration` tests. Passing `-m`
  on the command line replaces it.

## Root fixtures

The infrastructure fixtures are in `tests/conftest.py` and the app fixtures in
`tests/api/conftest.py`; read them rather than copying them. A test can rely on:

- The schema is built by the real migrations, never `BaseOrm.metadata.create_all()`.
- Each test runs inside one rolled-back transaction, and every session's `commit()` is
  a savepoint, so a service or route that commits needs no cleanup.
- `fastapi_app` runs the real lifespan and is function-scoped: never clear
  `dependency_overrides`, and every route test starts with an empty Redis.
- Tests never create or drop databases.

## §1 Pure unit tests

These are sync tests with no fixtures, covering prompts, model validators, enum
dispatch maps, and DTO mappers that contain logic.

| Situation                          | Pattern |
| ---------------------------------- | ------- |
| Prompt builder                     | Call it with distinctive input values and assert each one appears in the prompt it belongs in, system or user. Never snapshot the whole prompt. See `tests/libs/generate_text/graphs/blog_post/prompts/` |
| Template placeholder never filled  | No separate test: calling every builder once covers it |
| Validator or `Field` constraint    | One parametrized test of accepted values, one of rejected values raising `ValidationError` |
| Enum dispatch map                  | Parametrize over every member and assert each has a handler. The only allowed read of a `_private` attribute |
| DTO mapper with logic              | Build the DTO, call the mapper, compare the whole returned model |

## §2 Service tests

Build the service directly with stubs and an explicit settings object. No app, no
HTTP. If construction takes a client stack, move it into a fixture in the domain's
`conftest.py`. A test of a sync method that never touches a collaborator may pass
`None` for it, rather than a stub written only to satisfy `__init__`.

| Situation                         | Pattern |
| --------------------------------- | ------- |
| Happy path                        | Configure stubs, call the method, compare the whole `Result` |
| Collaborator gets the right input | Assert the stub's `<method>_inputs == [expected_input]` |
| Collaborator raises               | Set the stub's `<method>_error`, then `pytest.raises` whatever the service is meant to raise |
| One branch per enum member or flag | One test per branch, or parametrize if only data differs |
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

These are service tests that take the `db_session` fixture.

| Situation                         | Pattern |
| --------------------------------- | ------- |
| Create                            | Call, then `select()` the row back and assert on it. The returned `Result` alone proves nothing about persistence |
| Primary key and server defaults   | Assert `id` and `identity` are set and `created_at is not None`. Never assert an exact timestamp |
| Soft delete                       | Assert the ORM `select()` no longer finds the row and a raw `text()` select still does, with `deleted_by_id` set and `deleted_at` equal to the database's now. A raw `text()` select returns naive datetimes: compare `deleted_at.replace(tzinfo=UTC) == database_utc_now` |
| Audit columns                     | Assert `created_by_id` / `updated_by_id` equal the `AuthUser` the test passed in |
| Read, found                       | `insert_*_row`, call, compare the whole `Result` built from the row's values |
| Read, not found                   | Call with a key that was never inserted and `pytest.raises(NotFoundException)` |
| Update                            | Insert, call, select back, and assert both the changed and unchanged columns |
| Validation service (`validate_<condition>()`) | Insert the conflicting row, then `pytest.raises` the lib exception; add a case for each row the check must ignore (another user's, soft-deleted, the row being edited). No test for the raw constraint: a service's writes don't translate constraint violations (`fastapi-structure.md` › Database) |
| Relationships                     | Insert the parent and at least one child, and assert the child appears. A missing `selectinload()` fails as `MissingGreenlet` |
| Lists                             | Insert rows out of order. If the method promises an order, assert the exact list; otherwise compare sorted |
| Enum column                       | Parametrize a write-and-read round trip over every member |
| Failure partway through a write   | Trigger the failure, then select and assert no partial rows |

Link child rows by foreign key (`user_id=`), never with `parent.children.append()`.
Appending triggers a lazy load in async code.

## §4 Third-party HTTP APIs

Use the real SDK client, built over `httpx.MockTransport`, so one test checks both the
request the SDK built and how we parse the reply.

| Situation                         | Pattern |
| --------------------------------- | ------- |
| Success                           | Queue a response built from `tests/payloads/<provider>.py` and compare the whole `Result` |
| Request shape                     | Read `handle_requests[0]` and assert the path, plus body fields that come from settings (model, max tokens) |
| 4xx or 5xx                        | Parametrize the status code, queue the provider's error body, `pytest.raises` the lib or standard exception the service raises |
| No hidden retries                 | On error cases, assert `len(handle_requests) == 1` |
| Timeout or connection failure     | Set `handle_error = httpx.ReadTimeout(...)` or `httpx.ConnectError(...)`, then `pytest.raises` the lib or standard exception the service raises |
| Malformed or partial body         | Build the payload with a field set to `None` or missing, then `pytest.raises` the lib or standard exception the service raises |

- `HttpHandlerStub` (`tests/stubs/http.py`) records `handle_requests`, raises the
  queued `handle_errors` and then `handle_error`, and pops `handle_responses`.
- Build the service in the domain's `conftest.py` over
  `httpx.MockTransport(handler_stub.handle)`; `tests/libs/llm/conftest.py` is the
  pattern.
- Build SDK clients with `max_retries=0`. Otherwise every error case sleeps through
  the SDK's retry backoff.
- Payload builders copy a real captured response, with keyword parameters for the
  fields tests vary.

## §5 Redis

These tests take the `redis_client` fixture: real Redis, database index 15, flushed
before and after each test. See `tests/libs/auth/test_auth_session_service.py`.

| Situation                  | Pattern |
| -------------------------- | ------- |
| Key written                | Call, then read the key back with `redis_client.get` and assert the stored value |
| TTL set                    | Bind `await redis_client.ttl(key)` and assert `0 < ttl <= <setting value>` |
| Expired key                | Delete the key, which is what expiry looks like to the service. Call and assert it's treated as missing. Never sleep |
| Delete (logout)            | Call, bind `await redis_client.exists(key)`, assert `0` |
| Counter below, at, over a cap | Pre-set the counter with `redis_client.set(key, n)`, call, and assert allowed or `pytest.raises` the lib exception (a `RateLimitedException` subclass). An exempt user at the cap is allowed |
| Key and cookie names       | Assert the literal (`"session:..."`), not the imported constant. These `constants.py` values must match deployed data, and a test that reuses the constant can't catch a change |

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

**Signed-in requests go through the real guard.** Never override `get_auth_user`
(`AuthUserDep`). `build_auth_user` (`tests/factories/auth.py`) gives a role its seeded
permissions unless the test passes others. `signed_in_user` is a creator with every
non-admin permission and $5.00, enough to start a run; `signed_in_reader` holds only
the persona and blog post reads and `signed_in_admin` every permission, both with $0;
`other_user_client` is a second creator with its own client.

| Situation                     | Pattern |
| ----------------------------- | ------- |
| Happy path                    | Request bodies and expected responses are dict literals, never `Dto(...).model_dump()`: the test pins the JSON contract. Assert the status and the whole `response.json()` |
| Validation → 422              | Parametrize one missing required field plus one case per constraint the DTO declares. Assert the status and `detail[0]["loc"]`, never the message |
| Exception → status            | Set up the real condition (insert the duplicate row), or set the stub's `<method>_error`. Assert the status; assert the `{"detail": ...}` body only when the message is user-facing contract text |
| Create (`POST`)               | Select the row by the returned `identity` and assert its columns. The body is `{"identity": "<uuid>"}` |
| Malformed identity → 422      | One test per route with an identity path parameter: a non-UUID value returns 422 |
| Update (`PUT`) or `DELETE`    | Assert the body `== {}`, then select to prove the row changed or is gone. `await db_session.refresh(<entity>_record)` before reading a row the test already holds: `expire_on_commit=False` leaves its copy stale |
| Page or list (`GET` with a query model) | An invalid query value → 422 with `loc` starting `"query"`. A page also: an out-of-range `page` or `page_size` and a `sort_by` the route doesn't allow are 422s; one test per filter in its `PaginationConfig`, one search case, and `pagination` in a whole-response comparison (`fastapi-structure.md` › Paged routes) |
| Write rolls back on failure   | Make the route fail after its first write; assert no row |
| Protected route, signed out   | One test per protected route using plain `api_client`; assert 401 |
| Open `/public` route          | Signed out with plain `api_client`; the owner, with `is_owner` true; another user, with `is_owner` false; a 404 for an entity hidden from others; a 401 for an invalid session cookie |
| Signed in without the route's permission | Except on admin routes, one test per route whose permission a reader lacks, with `signed_in_reader`; assert 403, and for a write, select to prove nothing was written or changed. A read every role holds needs none: `test_dependencies.py` covers refusal |
| Another user's rows           | Create them through `other_user_client`, the way a real second user would, in a private `_create_*` helper kept in that test module, never in `factories/`. Never insert them with a factory in a route test, except on an admin route (next row) |
| Admin route                   | `signed_in_admin` for the happy path, `signed_in_user` (a creator) for the 403. Insert the target users with `insert_user_row`: an admin route acts on specific users with chosen values, such as a role, a balance or a `created_at`, which signing in through a second client can't set |
| Not found → 404               | Use an id that was never inserted |
| Redirect                      | Assert the status, then check `Location` with `urllib.parse` |
| Set-Cookie attributes         | Read `response.headers.get_list("set-cookie")`; assert `HttpOnly`, `Secure` for the environment, and `SameSite` |
| Rate limit → 429              | Pre-set the Redis counter at the cap; assert 429 |
| Not per route                 | Invalid or expired sessions (`tests/libs/auth/test_auth_session_service.py`) and unhandled 500s (`tests/api/core/test_exception_handlers.py`) are covered once |

```python
# tests/api/forecast_digest/test_router.py
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
```

## §7 App-wide behaviour

`tests/api/core/test_exception_handlers.py`, `tests/api/core/test_dependencies.py`,
`tests/api/test_lifespan.py` and `tests/api/test_app_factory.py` already exist. When
you change what they cover, extend the matching test:

- A new standard exception gets a new `pytest.param` in the status-code test, written
  as a literal, never looped from `STATUS_CODE_BY_EXCEPTION`.
- A new `app.state` resource: assert it's present inside `lifespan_context` and closed
  after it exits.
- A new route open by design goes on the allowlist in `test_app_factory.py`
  (`fastapi-structure.md` › The acting user).

To test app-wide behaviour without a domain route, add a throwaway route to the test's
`fastapi_app` inside the test body. A test that needs the 500 response builds its
client with `ASGITransport(..., raise_app_exceptions=False)`.

## §8 Settings

`tests/api/core/test_config.py` builds `AppSettings()` after
`monkeypatch.chdir(tmp_path)`, which keeps the repo's `config.toml` and any `.env` out
of the test, and calls `monkeypatch.delenv(<name>, raising=False)` for every variable
the test is about, in case the developer's shell sets it. A new nested settings group
gets an env-override case there.

## §9 Logging and middleware

| Situation                         | Pattern |
| --------------------------------- | ------- |
| A log event is a requirement (token counts per LLM call, see §12) | Wrap the act in `structlog.testing.capture_logs()`; find the event by name and assert its keys. See `tests/libs/llm/test_llm_call_service.py` |
| A job must end quietly            | `drain` never re-raises, so a failure is only logged as `background_job_failed`. Wrap the drain in `capture_logs()` and assert no event has that name |
| Request-id middleware             | A route test on any route: the response carries the header, and a header sent in is echoed back |
| Not tested                        | Log formatting, renderer output, Logfire export |

## §10 Migrations

`tests/migrations/test_revisions.py` covers every revision: one head, each `.up.sql`
has a `.down.sql`, and the stairway. A new migration needs no new test. The stairway
test is marked `migration` and runs on its own (`uv run pytest -m migration`), because
rebuilding the schema mid-run breaks asyncpg's cached type ids for the database tests
that follow.

## §11 LangGraph workflows

`langgraph.md` says where nodes, states and graphs live. A routing function is private
and covered by whole-run tests, never called directly. A node that calls `interrupt()`
can't run outside a graph, so it is covered the same way. See
`tests/libs/generate_text/graphs/blog_post/test_graph_builder.py`.

| Situation                   | Pattern |
| --------------------------- | ------- |
| Node                        | Take it from `get_node(<Domain>NodeType.X)` and call it with a state: stubs in, assert the returned state update |
| Every node type has a node  | Parametrize over `list(<Domain>NodeType)` and assert `get_node` returns one for each |
| Whole run                   | Compile with `InMemorySaver` and stubs whose `<method>_results` are scripted per pass. `ainvoke`, then assert the final state and the stub's call count |
| Loop bound                  | The stub never meets the exit condition. Assert the graph stops at the settings limit, not at a recursion error |
| Human review interrupt      | `ainvoke` to the interrupt, then assert `aget_state(...).interrupts[0].value` carries the paused payload |
| Resume after review         | From the interrupt, `ainvoke(Command(resume=...))` and assert where the graph went: publish on approval, back to rewrite on rejection |

## §12 Live LLM tests

Mark these `@pytest.mark.live_llm`. They're deselected by default and never run in
CI. Run them by hand with `LIVE_OPENAI_API_KEY=... uv run pytest -m live_llm`.

- Read the key from `LIVE_OPENAI_API_KEY`. The root fixture overwrites
  `OPENAI_API_KEY` with a fake. If the variable is missing, call `pytest.skip`.
- Test the contract only: the real response parses into our `Result`, the content
  isn't empty, token counts are positive.
- Never assert on wording. A human judges prompt quality, not pytest.
- Keep it to one or two tests, since they cost money.
