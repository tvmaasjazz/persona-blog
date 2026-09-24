from libs.generate_text.constants import GENERATE_BLOG_POST_PURPOSE, REWRITE_BLOG_POST_PURPOSE
from libs.generate_text.nodes import rewrite_blog_post, write_blog_post
from libs.llm.inputs import LlmCompletionInput
from libs.llm.types import LlmType
from tests.factories.generate_text import build_generate_text_state
from tests.factories.llm import build_llm_completion_result
from tests.stubs.llm import LlmServiceStub

# review_blog_post calls interrupt(), which only behaves correctly inside a running
# graph, so it's covered through the graph in test_graphs.py instead of directly here.


async def test_write_blog_post_sends_prompt_and_returns_draft() -> None:
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="A draft about coffee.")
    generate_text_state = build_generate_text_state(prompt_text="Write about coffee.")

    write_blog_post_result = await write_blog_post(
        generate_text_state, llm_service=llm_service_stub
    )

    assert llm_service_stub.complete_inputs == [
        LlmCompletionInput(
            llm_type=LlmType.STRONG,
            purpose=GENERATE_BLOG_POST_PURPOSE,
            system_prompt="You are a skilled writer producing text for a human editor to review.",
            user_prompt="Write a blog post based on the following brief:\n\nWrite about coffee.",
        )
    ]
    assert write_blog_post_result == {"draft_text": "A draft about coffee."}


async def test_rewrite_blog_post_sends_feedback_and_increments_rewrite_count() -> None:
    llm_service_stub = LlmServiceStub()
    llm_service_stub.complete_result = build_llm_completion_result(content="A revised draft.")
    generate_text_state = build_generate_text_state(
        draft_text="A draft about coffee.", feedback_text="Make it shorter.", rewrite_count=1
    )

    rewrite_blog_post_result = await rewrite_blog_post(
        generate_text_state, llm_service=llm_service_stub
    )

    assert llm_service_stub.complete_inputs == [
        LlmCompletionInput(
            llm_type=LlmType.STRONG,
            purpose=REWRITE_BLOG_POST_PURPOSE,
            system_prompt="You are a skilled writer producing text for a human editor to review.",
            user_prompt=(
                "Here is the current draft:\n\nA draft about coffee.\n\n"
                "A reviewer left the following feedback. Rewrite the draft to address it:\n\n"
                "Make it shorter."
            ),
        )
    ]
    assert rewrite_blog_post_result == {"draft_text": "A revised draft.", "rewrite_count": 2}
