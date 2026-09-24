from libs.generate_text.prompts import GenerateTextPrompt
from libs.generate_text.types import TextType


def test_build_system_prompt_returns_reviewer_instructions() -> None:
    system_prompt = GenerateTextPrompt.build_system_prompt()

    assert "skilled writer" in system_prompt
    assert "human editor" in system_prompt


def test_build_user_prompt_includes_prompt_text_and_text_type() -> None:
    user_prompt = GenerateTextPrompt.build_user_prompt("Write about coffee.", TextType.BLOG_POST)

    assert "Write about coffee." in user_prompt
    assert "blog post" in user_prompt


def test_build_rewrite_user_prompt_includes_draft_and_feedback() -> None:
    rewrite_user_prompt = GenerateTextPrompt.build_rewrite_user_prompt(
        "A draft about coffee.", "Make it shorter."
    )

    assert "A draft about coffee." in rewrite_user_prompt
    assert "Make it shorter." in rewrite_user_prompt
