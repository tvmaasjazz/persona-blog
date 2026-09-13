---
paths:
  - "backend/**/*.py"
---

# Python naming

Every name is explicit and self-describing. A reader should know the domain and the
kind of thing from the name alone, with no surrounding context: `AccountRouter`,
`HumanizerSettings`, `PersonaOrm`. No bare `Config`, `Manager`, `Helper`, `Utils`,
`data`, `obj`, `tmp`.

## Class suffixes

Every class ends in the suffix for what it is:

| Suffix       | Use for                                      | Example                          |
| ------------ | -------------------------------------------- | -------------------------------- |
| `Type`       | Enums                                        | `WritingType.BLOG_POST`          |
| `Settings`   | Config models: the root `AppSettings` (`BaseSettings`) and each domain's frozen `BaseModel` | `HumanizerSettings` |
| `Prompt`     | A grouped set of LLM prompt builders         | `HumanizerPrompt`                |
| `Input`      | A service method's payload (`libs/` only)    | `CreateUserInput`                |
| `Result`     | A function's return shape                    | `GetUserByEmailResult`           |
| `Router`     | FastAPI `APIRouter` modules                  | `account_router` (an `APIRouter` instance) |
| `Service`    | Business logic, framework-free               | `AccountService`                 |
| `Middleware` | ASGI / FastAPI middleware                    | `RequestLogMiddleware`           |
| `Dto`        | Inbound HTTP body (`apps/` only)             | `BlogPostDto`, `GenerateWritingDto` |
| `QueryDto`   | A list route's query model (`apps/` only)    | `BlogPostFetchAllQueryDto`       |
| `ResponseDto`| A route's response shape (`apps/` only)      | `BlogPostResponseDto`, `IdentityResponseDto` |
| `Orm`        | SQLAlchemy table classes                     | `UserOrm`, `PersonaOrm`          |
| `Key`        | Defined key objects                          | `CacheKey`, `StateKey`           |
| `Exception`  | Exceptions: standard ones in `libs/core/`, domain-prefixed ones in their lib | `NotFoundException`, `AiWriteInappropriateException` |
| `Stub`       | A hand-written test double (`tests/` only)   | `LlmServiceStub`, `HttpHandlerStub` |
| `Model`      | Only when the purpose is genuinely unclear   | —                                |

A `Result` is named for **the function that returns it**, not the entity it carries:
`GetUserByEmailResult`, `CreateUserResult`, `HumanizeDraftResult`. `UserResult` says
nothing about what the shape is for. If two functions genuinely return an identical
shape, reuse one class named for the shape's meaning (`UserDetailResult`) rather than
duplicating — but never fall back to a bare entity name.

Never use the word `Schema`. A Pydantic class at the HTTP boundary is a `Dto`; one
returned by a service is a `Result`.

`Model` is a smell, not a default. If you use it, say so explicitly in your summary
so Tyler can review and rename it.

## Enums

Enums are `StrEnum`, and **the member name and its string value are identical, both
`UPPER_SNAKE`**:

```python
class WritingType(StrEnum):
    BLOG_POST = "BLOG_POST"
    NEWSLETTER = "NEWSLETTER"
```

Write the value out explicitly. Never `auto()` — in a `StrEnum` it produces the
lowercased member name, which breaks the rule silently.

This carries into the database. A Postgres enum type's labels are `UPPER_SNAKE` and
match the Python members exactly; the type itself is named in snake_case after the
class (`WritingType` → `writing_type`). SQLAlchemy's `Enum` column persists member
*names* by default while Pydantic serializes *values* — when the two are identical,
that difference stops being a source of bugs.

```sql
-- migrations/sql/posts/0001_create_posts.up.sql
CREATE TYPE writing_type AS ENUM ('BLOG_POST', 'NEWSLETTER');
```

Adding a member means a migration (`ALTER TYPE ... ADD VALUE`) in the same commit as
the Python change.

## Enum dispatch

When each enum value needs a different function, never `if/elif` over the enum.
Build a dispatch map in `__init__` and look the handler up:

```python
from enum import StrEnum


class CommandType(StrEnum):
    START = "START"
    STOP = "STOP"
    PAUSE = "PAUSE"


class ExecutionEngine:
    def __init__(self) -> None:
        self._dispatch_map = {
            CommandType.START: self._execute_start,
            CommandType.STOP: self._execute_stop,
            CommandType.PAUSE: self._execute_pause,
        }

    def run(self, command: CommandType) -> None:
        handler = self._dispatch_map.get(command)
        if not handler:
            raise NotImplementedError(f"No handler registered for {command}")
        handler()

    def _execute_start(self) -> None: ...
```

Adding an enum member without a map entry must fail loudly at call time, which the
`NotImplementedError` above gives you.

## Variables

A variable name says what the thing *is*, including the qualifier that makes it
unambiguous. Bare infrastructure nouns are banned — there is more than one kind of
session, client, and config in this codebase:

| Not this   | This                                        |
| ---------- | ------------------------------------------- |
| `session`  | `db_session`                                |
| `client`   | `http_client`, `llm_client`, `storage_client` |
| `config`   | `humanizer_settings`                        |
| `result`   | `query_result`, `humanize_result`           |
| `service`  | `user_service`, `humanizer_service`         |
| `data`     | name the actual contents                    |

This extends to attributes (`self._db_session`), constructor parameters, dependency
factories (`get_db_session`, `db_session_factory`), and anything on `app.state`. If a
name would still be correct in an unrelated module, it is too generic.

## Statements and readability

**An `await` result is bound to a name unless it is returned directly or unused.** An
`await` expression may appear in exactly three places: as the whole right-hand side of
an assignment, immediately after `return`, or as a statement on its own when its value
is unused. If its value is wrapped in a call, passed as an argument, subscripted, or
attribute-accessed, bind it to a variable first.

```python
# no — the awaited value is being wrapped
return UserResponseDto.from_result(await user_service.get_user(user_id))

# yes
get_user_result = await user_service.get_user(user_id)
return UserResponseDto.from_result(get_user_result)

# also fine — returned directly, nothing wrapping it
return await user_service.get_user(user_id)

# also fine — a statement on its own, the value is unused
await user_service.delete_user(user_id)
await redis_client.flushdb()
```

**At most two calls per statement.** Three or more means splitting the line, even
when it fits in the line limit. A single nested call that reads as one thought is
fine — `service.create_user(dto.to_input())` is two calls and stays — but a third
level of nesting hides the order of operations.

```python
# no — three calls
posts = list(sorted(persona.posts(), key=lambda p: p.created_at))

# yes
raw_posts = persona.posts()
posts = sorted(raw_posts, key=lambda p: p.created_at)
```

The same applies to chained attribute access into a call:
`(await get_user(user_id)).persona.name` becomes three lines, not one clever one.

## Other conventions

- Type-hint every function signature, parameters and return.
- Private methods and attributes are `_`-prefixed; anything without `_` is API.
- Functions returning more than one value return a `...Result` Pydantic model, not a
  tuple or a dict.
- Module filenames are short inside a domain package, since the folder already
  names the domain: `domains/users/router.py`, `libs/users/services.py`. Never
  `users/user_router.py`. Class and object names stay fully explicit regardless.
- Enum members are `UPPER_SNAKE`. Constants are `UPPER_SNAKE` at module level.
