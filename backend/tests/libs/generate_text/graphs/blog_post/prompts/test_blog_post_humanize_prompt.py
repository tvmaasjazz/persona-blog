from libs.generate_text.graphs.blog_post.blog_post_body_output_format import (
    BLOG_POST_BODY_FORMAT_RULES,
)
from libs.generate_text.graphs.blog_post.prompts import BlogPostHumanizePrompt
from tests.factories.generate_text import build_generate_text_state


def test_build_generate_prompt_includes_format_rules_in_system_prompt() -> None:
    state = build_generate_text_state()

    build_prompt_result = BlogPostHumanizePrompt().build_generate_prompt(state)

    assert BLOG_POST_BODY_FORMAT_RULES in build_prompt_result.system_prompt


def test_build_generate_prompt_puts_used_persona_fields_in_system_prompt() -> None:
    state = build_generate_text_state(
        persona_name="Marta Quill",
        persona_writing_style="Short punchy sentences.",
        persona_sample_writing="The starter bubbled all night.",
    )

    build_prompt_result = BlogPostHumanizePrompt().build_generate_prompt(state)

    assert "Marta Quill" in build_prompt_result.system_prompt
    assert "Short punchy sentences." in build_prompt_result.system_prompt
    assert "The starter bubbled all night." in build_prompt_result.system_prompt


def test_build_generate_prompt_omits_fields_the_step_does_not_use() -> None:
    state = build_generate_text_state(
        persona_bio="Writes about sourdough.",
        persona_background="Former baker.",
    )

    build_prompt_result = BlogPostHumanizePrompt().build_generate_prompt(state)

    assert "Writes about sourdough." not in build_prompt_result.system_prompt
    assert "Former baker." not in build_prompt_result.system_prompt


def test_build_generate_prompt_puts_tone_and_target_audience_in_system_prompt() -> None:
    state = build_generate_text_state(tone="Playful", target_audience="Home bakers")

    build_prompt_result = BlogPostHumanizePrompt().build_generate_prompt(state)

    assert "Playful" in build_prompt_result.system_prompt
    assert "Home bakers" in build_prompt_result.system_prompt


def test_build_generate_prompt_omits_empty_tone_and_target_audience() -> None:
    state = build_generate_text_state(tone=None, target_audience=None)

    build_prompt_result = BlogPostHumanizePrompt().build_generate_prompt(state)

    assert "Tone:" not in build_prompt_result.system_prompt
    assert "Target audience:" not in build_prompt_result.system_prompt


def test_build_generate_prompt_puts_draft_in_user_prompt() -> None:
    state = build_generate_text_state(
        step_outputs={"GENERATE_DRAFT": "A full draft about sourdough."}
    )

    build_prompt_result = BlogPostHumanizePrompt().build_generate_prompt(state)

    assert "A full draft about sourdough." in build_prompt_result.user_prompt


def test_build_generate_prompt_puts_additional_context_in_user_prompt() -> None:
    state = build_generate_text_state(additional_context="Reference: https://example.com/guide")

    build_prompt_result = BlogPostHumanizePrompt().build_generate_prompt(state)

    assert "Reference: https://example.com/guide" in build_prompt_result.user_prompt


def test_build_generate_prompt_omits_empty_additional_context() -> None:
    state = build_generate_text_state(additional_context=None)

    build_prompt_result = BlogPostHumanizePrompt().build_generate_prompt(state)

    assert "Additional context:" not in build_prompt_result.user_prompt


def test_build_rewrite_prompt_puts_previous_output_and_feedback_in_user_prompt() -> None:
    state = build_generate_text_state(prompt_text="Write about sourdough starters.")

    build_prompt_result = BlogPostHumanizePrompt().build_rewrite_prompt(
        state, "A humanized draft.", "Sound less robotic."
    )

    assert "A humanized draft." in build_prompt_result.user_prompt
    assert "Sound less robotic." in build_prompt_result.user_prompt


def test_build_rewrite_prompt_omits_the_brief() -> None:
    state = build_generate_text_state(prompt_text="Write about sourdough starters.")

    build_prompt_result = BlogPostHumanizePrompt().build_rewrite_prompt(
        state, "A humanized draft.", "Sound less robotic."
    )

    assert "Write about sourdough starters." not in build_prompt_result.user_prompt


def test_build_rewrite_prompt_shares_generate_prompts_system_prompt() -> None:
    state = build_generate_text_state(persona_name="Marta Quill")

    generate_result = BlogPostHumanizePrompt().build_generate_prompt(state)
    rewrite_result = BlogPostHumanizePrompt().build_rewrite_prompt(state, "draft", "feedback")

    assert rewrite_result.system_prompt == generate_result.system_prompt
