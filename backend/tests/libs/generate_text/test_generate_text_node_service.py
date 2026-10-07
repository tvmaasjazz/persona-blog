import pytest

from libs.generate_text.exceptions import GenerateTextOutputInvalidException
from libs.generate_text.graphs.blog_post.blog_post_body_output_format import (
    BlogPostBodyOutputFormat,
)
from libs.generate_text.services.generate_text_node_service import GenerateTextNodeService
from libs.generate_text.settings import GenerateTextSettings
from libs.generate_text.types import GenerateTextNodeType
from libs.llm.types import LlmType
from tests.factories.generate_text import build_generate_text_state
from tests.factories.llm import build_llm_completion_result
from tests.stubs.generate_text import GenerateTextPromptStub
from tests.stubs.llm import LlmServiceStub

VALID_BODY_TEXT = "# Sourdough Starters\n\nFeed it daily."


async def test_build_generate_node_sends_system_and_user_prompt_from_prompt_object() -> None:
    llm_service_stub = LlmServiceStub()
    generate_text_node_service = GenerateTextNodeService(
        llm_service=llm_service_stub, generate_text_settings=GenerateTextSettings()
    )
    generate_text_prompt_stub = GenerateTextPromptStub()
    generate_node = generate_text_node_service.build_generate_node(
        GenerateTextNodeType.GENERATE_DRAFT, LlmType.STRONG, generate_text_prompt_stub
    )
    generate_text_state = build_generate_text_state()

    await generate_node(generate_text_state)

    sent_completion_input = llm_service_stub.complete_inputs[0]
    assert sent_completion_input.system_prompt == "Stub generate system prompt."
    assert sent_completion_input.user_prompt == "Stub generate user prompt."


async def test_build_generate_node_appends_content_to_step_outputs() -> None:
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="A generated draft.")
    generate_text_node_service = GenerateTextNodeService(
        llm_service=llm_service_stub, generate_text_settings=GenerateTextSettings()
    )
    generate_node = generate_text_node_service.build_generate_node(
        GenerateTextNodeType.GENERATE_DRAFT, LlmType.STRONG, GenerateTextPromptStub()
    )
    generate_text_state = build_generate_text_state(
        step_outputs={"GENERATE_OUTLINE": "An outline."}
    )

    generate_node_result = await generate_node(generate_text_state)

    assert generate_node_result == {
        "step_outputs": {
            "GENERATE_OUTLINE": "An outline.",
            "GENERATE_DRAFT": "A generated draft.",
        }
    }


async def test_build_rewrite_node_sends_system_and_user_prompt_from_prompt_object() -> None:
    llm_service_stub = LlmServiceStub()
    generate_text_node_service = GenerateTextNodeService(
        llm_service=llm_service_stub, generate_text_settings=GenerateTextSettings()
    )
    generate_text_prompt_stub = GenerateTextPromptStub()
    rewrite_node = generate_text_node_service.build_rewrite_node(
        GenerateTextNodeType.REWRITE_DRAFT,
        LlmType.STRONG,
        GenerateTextNodeType.REVIEW_DRAFT,
        generate_text_prompt_stub,
    )
    generate_text_state = build_generate_text_state(
        step_outputs={"GENERATE_DRAFT": "A draft."},
        step_feedback={"REVIEW_DRAFT": "Make it shorter."},
    )

    await rewrite_node(generate_text_state)

    sent_completion_input = llm_service_stub.complete_inputs[0]
    assert sent_completion_input.system_prompt == "Stub rewrite system prompt."
    assert sent_completion_input.user_prompt == "Stub rewrite user prompt."


async def test_build_rewrite_node_appends_content_and_increments_rewrite_count() -> None:
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="A revised draft.")
    generate_text_node_service = GenerateTextNodeService(
        llm_service=llm_service_stub, generate_text_settings=GenerateTextSettings()
    )
    rewrite_node = generate_text_node_service.build_rewrite_node(
        GenerateTextNodeType.REWRITE_DRAFT,
        LlmType.STRONG,
        GenerateTextNodeType.REVIEW_DRAFT,
        GenerateTextPromptStub(),
    )
    generate_text_state = build_generate_text_state(
        step_outputs={"GENERATE_DRAFT": "A draft."},
        step_feedback={"REVIEW_DRAFT": "Make it shorter."},
        rewrite_counts={"REVIEW_DRAFT": 1},
    )

    rewrite_node_result = await rewrite_node(generate_text_state)

    assert rewrite_node_result == {
        "step_outputs": {
            "GENERATE_DRAFT": "A draft.",
            "REWRITE_DRAFT": "A revised draft.",
        },
        "rewrite_counts": {"REVIEW_DRAFT": 2},
    }


async def test_build_generate_node_output_format_none_passes_content_through_untouched() -> None:
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="not markdown at all")
    generate_text_node_service = GenerateTextNodeService(
        llm_service=llm_service_stub, generate_text_settings=GenerateTextSettings()
    )
    generate_node = generate_text_node_service.build_generate_node(
        GenerateTextNodeType.GENERATE_DRAFT, LlmType.STRONG, GenerateTextPromptStub()
    )
    generate_text_state = build_generate_text_state()

    generate_node_result = await generate_node(generate_text_state)

    assert generate_node_result == {
        "step_outputs": {"GENERATE_DRAFT": "not markdown at all"},
    }
    assert len(llm_service_stub.complete_inputs) == 1


async def test_build_generate_node_valid_output_first_time_calls_llm_once() -> None:
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content=VALID_BODY_TEXT)
    generate_text_node_service = GenerateTextNodeService(
        llm_service=llm_service_stub, generate_text_settings=GenerateTextSettings()
    )
    generate_node = generate_text_node_service.build_generate_node(
        GenerateTextNodeType.GENERATE_DRAFT,
        LlmType.STRONG,
        GenerateTextPromptStub(),
        BlogPostBodyOutputFormat(),
    )
    generate_text_state = build_generate_text_state()

    generate_node_result = await generate_node(generate_text_state)

    assert generate_node_result == {"step_outputs": {"GENERATE_DRAFT": VALID_BODY_TEXT}}
    assert len(llm_service_stub.complete_inputs) == 1


async def test_build_generate_node_fenced_output_stored_unwrapped_with_no_retry() -> None:
    llm_service_stub = LlmServiceStub()
    fenced_body_text = f"```markdown\n{VALID_BODY_TEXT}\n```"
    llm_service_stub.complete_result = build_llm_completion_result(content=fenced_body_text)
    generate_text_node_service = GenerateTextNodeService(
        llm_service=llm_service_stub, generate_text_settings=GenerateTextSettings()
    )
    generate_node = generate_text_node_service.build_generate_node(
        GenerateTextNodeType.GENERATE_DRAFT,
        LlmType.STRONG,
        GenerateTextPromptStub(),
        BlogPostBodyOutputFormat(),
    )
    generate_text_state = build_generate_text_state()

    generate_node_result = await generate_node(generate_text_state)

    assert generate_node_result == {"step_outputs": {"GENERATE_DRAFT": VALID_BODY_TEXT}}
    assert len(llm_service_stub.complete_inputs) == 1


async def test_build_generate_node_invalid_then_valid_retries_once_with_problems_in_prompt() -> (
    None
):
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_results = [
        build_llm_completion_result(content="not valid markdown"),
        build_llm_completion_result(content=VALID_BODY_TEXT),
    ]
    generate_text_node_service = GenerateTextNodeService(
        llm_service=llm_service_stub, generate_text_settings=GenerateTextSettings()
    )
    generate_node = generate_text_node_service.build_generate_node(
        GenerateTextNodeType.GENERATE_DRAFT,
        LlmType.STRONG,
        GenerateTextPromptStub(),
        BlogPostBodyOutputFormat(),
    )
    generate_text_state = build_generate_text_state()

    generate_node_result = await generate_node(generate_text_state)

    assert generate_node_result == {"step_outputs": {"GENERATE_DRAFT": VALID_BODY_TEXT}}
    assert len(llm_service_stub.complete_inputs) == 2
    second_user_prompt = llm_service_stub.complete_inputs[1].user_prompt
    assert "problems" in second_user_prompt.lower()
    assert "Stub generate user prompt." in second_user_prompt


async def test_build_generate_node_invalid_twice_raises_with_problems_in_message() -> None:
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="not valid markdown")
    generate_text_node_service = GenerateTextNodeService(
        llm_service=llm_service_stub, generate_text_settings=GenerateTextSettings()
    )
    generate_node = generate_text_node_service.build_generate_node(
        GenerateTextNodeType.GENERATE_DRAFT,
        LlmType.STRONG,
        GenerateTextPromptStub(),
        BlogPostBodyOutputFormat(),
    )
    generate_text_state = build_generate_text_state()

    with pytest.raises(GenerateTextOutputInvalidException) as exception_info:
        await generate_node(generate_text_state)

    assert "The document must start with a single '# Title' heading" in str(exception_info.value)
    assert len(llm_service_stub.complete_inputs) == 2


async def test_build_generate_node_max_output_format_retries_zero_calls_once_then_raises() -> None:
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="not valid markdown")
    generate_text_node_service = GenerateTextNodeService(
        llm_service=llm_service_stub,
        generate_text_settings=GenerateTextSettings(max_output_format_retries=0),
    )
    generate_node = generate_text_node_service.build_generate_node(
        GenerateTextNodeType.GENERATE_DRAFT,
        LlmType.STRONG,
        GenerateTextPromptStub(),
        BlogPostBodyOutputFormat(),
    )
    generate_text_state = build_generate_text_state()

    with pytest.raises(GenerateTextOutputInvalidException):
        await generate_node(generate_text_state)

    assert len(llm_service_stub.complete_inputs) == 1
