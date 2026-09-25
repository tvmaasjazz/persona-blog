from libs.blog_post.prompts import BlogPostPrompt


def test_build_outline_prompt_includes_prompt_text() -> None:
    outline_prompt = BlogPostPrompt.build_outline_prompt(
        "Write about sourdough starters.", persona_info=None, additional_context=None
    )

    assert "Write about sourdough starters." in outline_prompt


def test_build_outline_prompt_includes_persona_info_and_additional_context() -> None:
    outline_prompt = BlogPostPrompt.build_outline_prompt(
        "Write about sourdough starters.",
        persona_info="Writes plainly, bakes at home.",
        additional_context="Reference: https://example.com/starter-guide",
    )

    assert "Writes plainly, bakes at home." in outline_prompt
    assert "Reference: https://example.com/starter-guide" in outline_prompt


def test_build_draft_prompt_includes_prompt_text_and_outline() -> None:
    draft_prompt = BlogPostPrompt.build_draft_prompt(
        "Write about sourdough starters.",
        "I. Intro II. Feeding schedule",
        persona_info=None,
        additional_context=None,
    )

    assert "Write about sourdough starters." in draft_prompt
    assert "I. Intro II. Feeding schedule" in draft_prompt


def test_build_draft_prompt_includes_persona_info_and_additional_context() -> None:
    draft_prompt = BlogPostPrompt.build_draft_prompt(
        "Write about sourdough starters.",
        "I. Intro",
        persona_info="Writes plainly.",
        additional_context="Reference: https://example.com",
    )

    assert "Writes plainly." in draft_prompt
    assert "Reference: https://example.com" in draft_prompt


def test_build_humanize_prompt_includes_draft_text() -> None:
    humanize_prompt = BlogPostPrompt.build_humanize_prompt(
        "A full draft about sourdough.", persona_info=None, additional_context=None
    )

    assert "A full draft about sourdough." in humanize_prompt


def test_build_humanize_prompt_includes_persona_info_and_additional_context() -> None:
    humanize_prompt = BlogPostPrompt.build_humanize_prompt(
        "A full draft about sourdough.",
        persona_info="Writes plainly.",
        additional_context="Reference: https://example.com",
    )

    assert "Writes plainly." in humanize_prompt
    assert "Reference: https://example.com" in humanize_prompt


def test_build_rewrite_outline_prompt_includes_previous_output_and_feedback() -> None:
    rewrite_outline_prompt = BlogPostPrompt.build_rewrite_outline_prompt(
        "I. Intro II. Feeding schedule",
        "Add a section on hydration ratios.",
        persona_info=None,
        additional_context=None,
    )

    assert "I. Intro II. Feeding schedule" in rewrite_outline_prompt
    assert "Add a section on hydration ratios." in rewrite_outline_prompt


def test_build_rewrite_outline_prompt_includes_persona_info_and_additional_context() -> None:
    rewrite_outline_prompt = BlogPostPrompt.build_rewrite_outline_prompt(
        "I. Intro",
        "Add hydration ratios.",
        persona_info="Writes plainly.",
        additional_context="Reference: https://example.com",
    )

    assert "Writes plainly." in rewrite_outline_prompt
    assert "Reference: https://example.com" in rewrite_outline_prompt


def test_build_rewrite_draft_prompt_includes_previous_output_and_feedback() -> None:
    rewrite_draft_prompt = BlogPostPrompt.build_rewrite_draft_prompt(
        "A full draft about sourdough.",
        "Make it shorter.",
        persona_info=None,
        additional_context=None,
    )

    assert "A full draft about sourdough." in rewrite_draft_prompt
    assert "Make it shorter." in rewrite_draft_prompt


def test_build_rewrite_draft_prompt_includes_persona_info_and_additional_context() -> None:
    rewrite_draft_prompt = BlogPostPrompt.build_rewrite_draft_prompt(
        "A full draft.",
        "Make it shorter.",
        persona_info="Writes plainly.",
        additional_context="Reference: https://example.com",
    )

    assert "Writes plainly." in rewrite_draft_prompt
    assert "Reference: https://example.com" in rewrite_draft_prompt


def test_build_rewrite_humanize_prompt_includes_previous_output_and_feedback() -> None:
    rewrite_humanize_prompt = BlogPostPrompt.build_rewrite_humanize_prompt(
        "A humanized draft.",
        "Sound less robotic.",
        persona_info=None,
        additional_context=None,
    )

    assert "A humanized draft." in rewrite_humanize_prompt
    assert "Sound less robotic." in rewrite_humanize_prompt


def test_build_rewrite_humanize_prompt_includes_persona_info_and_additional_context() -> None:
    rewrite_humanize_prompt = BlogPostPrompt.build_rewrite_humanize_prompt(
        "A humanized draft.",
        "Sound less robotic.",
        persona_info="Writes plainly.",
        additional_context="Reference: https://example.com",
    )

    assert "Writes plainly." in rewrite_humanize_prompt
    assert "Reference: https://example.com" in rewrite_humanize_prompt
