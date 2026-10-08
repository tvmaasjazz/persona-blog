from libs.generate_text.graphs.blog_post.blog_post_body_output_format import (
    BLOG_POST_BODY_FORMAT_RULES,
)
from libs.generate_text.graphs.blog_post.prompts import BlogPostOutlinePrompt
from tests.factories.generate_text import build_generate_text_state


def test_build_generate_prompt_excludes_format_rules_from_system_prompt() -> None:
    state = build_generate_text_state()

    build_prompt_result = BlogPostOutlinePrompt().build_generate_prompt(state)

    assert BLOG_POST_BODY_FORMAT_RULES not in build_prompt_result.system_prompt


def test_build_generate_prompt_puts_used_persona_fields_in_system_prompt() -> None:
    state = build_generate_text_state(
        persona_name="Marta Quill",
        persona_bio="Writes about sourdough.",
        persona_background="Former baker.",
    )

    build_prompt_result = BlogPostOutlinePrompt().build_generate_prompt(state)

    assert "Marta Quill" in build_prompt_result.system_prompt
    assert "Writes about sourdough." in build_prompt_result.system_prompt
    assert "Former baker." in build_prompt_result.system_prompt


def test_build_generate_prompt_omits_field_the_step_does_not_use() -> None:
    state = build_generate_text_state(
        persona_writing_style="Short punchy sentences.",
        persona_sample_writing="The starter bubbled all night.",
    )

    build_prompt_result = BlogPostOutlinePrompt().build_generate_prompt(state)

    assert "Short punchy sentences." not in build_prompt_result.system_prompt
    assert "The starter bubbled all night." not in build_prompt_result.system_prompt


def test_build_generate_prompt_puts_tone_and_target_audience_in_system_prompt() -> None:
    state = build_generate_text_state(tone="Playful", target_audience="Home bakers")

    build_prompt_result = BlogPostOutlinePrompt().build_generate_prompt(state)

    assert "Playful" in build_prompt_result.system_prompt
    assert "Home bakers" in build_prompt_result.system_prompt


def test_build_generate_prompt_omits_empty_tone_and_target_audience() -> None:
    state = build_generate_text_state(tone=None, target_audience=None)

    build_prompt_result = BlogPostOutlinePrompt().build_generate_prompt(state)

    assert "Tone:" not in build_prompt_result.system_prompt
    assert "Target audience:" not in build_prompt_result.system_prompt


def test_build_generate_prompt_puts_prompt_text_in_user_prompt() -> None:
    state = build_generate_text_state(prompt_text="Write about sourdough starters.")

    build_prompt_result = BlogPostOutlinePrompt().build_generate_prompt(state)

    assert "Write about sourdough starters." in build_prompt_result.user_prompt


def test_build_generate_prompt_puts_additional_context_in_user_prompt() -> None:
    state = build_generate_text_state(additional_context="Reference: https://example.com/guide")

    build_prompt_result = BlogPostOutlinePrompt().build_generate_prompt(state)

    assert "Reference: https://example.com/guide" in build_prompt_result.user_prompt


def test_build_generate_prompt_omits_empty_additional_context() -> None:
    state = build_generate_text_state(additional_context=None)

    build_prompt_result = BlogPostOutlinePrompt().build_generate_prompt(state)

    assert "Additional context:" not in build_prompt_result.user_prompt


def test_build_rewrite_prompt_puts_brief_output_and_feedback_in_user_prompt() -> None:
    state = build_generate_text_state(prompt_text="Write about sourdough starters.")

    build_prompt_result = BlogPostOutlinePrompt().build_rewrite_prompt(
        state, "I. Intro II. Feeding schedule", "Add a section on hydration ratios."
    )

    assert "Write about sourdough starters." in build_prompt_result.user_prompt
    assert "I. Intro II. Feeding schedule" in build_prompt_result.user_prompt
    assert "Add a section on hydration ratios." in build_prompt_result.user_prompt


def test_build_rewrite_prompt_shares_generate_prompts_system_prompt() -> None:
    state = build_generate_text_state(persona_name="Marta Quill")

    generate_result = BlogPostOutlinePrompt().build_generate_prompt(state)
    rewrite_result = BlogPostOutlinePrompt().build_rewrite_prompt(state, "outline", "feedback")

    assert rewrite_result.system_prompt == generate_result.system_prompt
