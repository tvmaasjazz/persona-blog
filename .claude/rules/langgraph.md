---
paths:
  - "backend/libs/**/graphs/**"
  - "backend/libs/**/states.py"
  - "backend/libs/**/prompts.py"
  - "backend/libs/**/prompts/**"
  - "backend/libs/**/output_formats.py"
  - "backend/libs/**/*node_service.py"
  - "backend/libs/llm/**"
  - "backend/tests/libs/**/graphs/**"
  - "backend/tests/libs/**/prompts/**"
  - "backend/tests/stubs/llm.py"
---

# LangGraph workflows and prompts

Everything else about a lib follows `fastapi-structure.md`.

## LangGraph workflows

A domain whose work is a graph keeps it under `libs/<domain>/`:

- `types.py` — `<Domain>NodeType`, one member per node. LangGraph takes a `StrEnum`
  member as the node name, so nothing refers to a node by a loose string.
- `states.py` — one `<Domain>State`, the graph's state model.
- `services/<domain>_node_service.py` — `<Domain>NodeService`, which builds the nodes.
  Collaborators arrive through `__init__` like any other service.
- `graphs/` — a package, not a module, once there is more than one graph:
  - `base_<domain>_graph_builder.py` — the abstract builder: `graph_name` and
    `graph_version` as class attributes, an abstract `build_graph(options, checkpointer)`,
    and the services every builder needs taken through `__init__`.
  - `<domain>_graph_builder_registry.py` — one builder per enum member, built in
    `__init__`, looked up by a `get_by_<enum>`-style method that raises
    `NotImplementedError` for a member with none (`python-naming.md` › Enum dispatch).
  - `<variant>/` — one folder per graph: its builder, its prompts, its options input.

Reference: `libs/generate_text/`.

A variant is not a lib of its own: splitting one out puts the engine and the variant in
a mutual import (`fastapi-structure.md` › Layer rules). The registry and the services
that need it break the same cycle inside the lib with `if TYPE_CHECKING:`.

**A graph state holds primitives only** — `str`, `int`, `bool`, `UUID`, and containers
of them. The Redis checkpointer returns a domain class as a
`{"lc": 2, "type": "constructor", ...}` envelope that no longer validates, and the
in-memory checkpointer in tests hides that because it never really serializes.

**Group primitives back into a shape with a method on the state**, rather than storing
the shape: `build_auth_user()` returns the `AuthUser` the state's user id and identity
describe. The stored checkpoint stays plain.

**A wrapper around a node re-raises `GraphBubbleUp` before any `except Exception`.**
LangGraph signals an interrupt by raising it, so a generic handler turns every review
pause into a recorded failure. Catch the control-flow exception first, record the pause
for what it is, and let it through.

**A step whose output must follow a format gets an `OutputFormat`**, passed to its
node builder beside its `Prompt`. `Base<Domain>OutputFormat`, in `output_formats.py`
beside `prompts.py`, has `normalize_output()`, which fixes in code only what can't
change the meaning (a fence wrapping the whole output, surrounding whitespace), and
`validate_output()`, which returns the problems left. The node normalizes, then
validates; on problems it retries the LLM call with them added to the user prompt, up
to a settings limit, then raises a lib exception under `ServiceUnavailableException`,
since the model, not the caller, produced the unusable output.

- Checking is code, never another LLM call. Parsing goes through a domain-free `Utils`
  class, such as `MarkdownUtils`.
- The format's rules text lives in the same module as the `OutputFormat`, and the
  step's system template uses it, so the instructions and the check can't drift apart.
- A graph variant's `OutputFormat` gets its own module directly in the variant's
  folder, beside its builder and its `prompts/` package.

The service owns the graph's lifecycle, not its shape: it asks the registry for the
builder, calls `build_graph`, runs it, reads the snapshot, and maps it to a `Result`.

## Prompts

Every LLM call takes a system prompt and a user prompt, and one `Prompt` class builds
both for one step. A domain whose steps share a shape declares an abstract
`Base<Domain>Prompt`, and each step extends it. A lib or graph variant with one prompt
class keeps it in `prompts.py`. One with more keeps them in a `prompts/` package, one
module per class named after it in snake_case, holding that class and its templates,
with `__init__.py` re-exporting every class. Reference:
`libs/generate_text/graphs/blog_post/prompts/`.

- The system prompt says what the model is expected to do, then who it is doing it
  as. The user prompt carries the material for this call.
- Every prompt a class returns is one template, formatted once, with everything passed
  in, including sections built by `_build_<what>_prompt_section` helpers. Never add to
  a formatted template afterwards. The helpers format with templates too, and a
  section that has nothing to say returns `""`.
- A rewrite is a method on its step's class, not a class of its own, so it shares the
  step's system prompt.
- Each class chooses which inputs it uses and where they go. Formatting shared by
  several steps is a protected helper on the base class; the subclass still decides
  what to pass it and which prompt it lands in.
- Method names are `build_<what>_prompt`. Never a bare `prompt()`. Every one returns a
  `BuildPromptResult` holding `system_prompt` and `user_prompt`.
- A prompt class holds no state. One needing configuration takes it through
  `__init__`, like a service.
- Template text is an `UPPER_SNAKE` constant at the top of the module that uses it.
  Never inline in the method. Prompt text that belongs to no single step, such as a
  node's retry instructions, follows the same rule in the module that uses it.
- A service or node never builds a prompt string inline.
