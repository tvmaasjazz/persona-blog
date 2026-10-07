import pytest

from libs.core.utils.markdown_utils import MarkdownUtils


@pytest.mark.parametrize(
    ("markdown_text", "expected_unwrapped_text"),
    [
        pytest.param("```\n# Title\n\nBody.\n```", "# Title\n\nBody.\n", id="bare_fence"),
        pytest.param(
            "```markdown\n# Title\n\nBody.\n```", "# Title\n\nBody.\n", id="markdown_fence"
        ),
        pytest.param("```md\n# Title\n\nBody.\n```", "# Title\n\nBody.\n", id="md_fence"),
    ],
)
def test_strip_wrapping_code_fence_unwraps_whole_document_fence(
    markdown_text: str, expected_unwrapped_text: str
) -> None:
    unwrapped_text = MarkdownUtils.strip_wrapping_code_fence(markdown_text)

    assert unwrapped_text == expected_unwrapped_text


def test_strip_wrapping_code_fence_disallowed_info_string_returns_unchanged() -> None:
    markdown_text = "```python\nprint('hi')\n```"

    unwrapped_text = MarkdownUtils.strip_wrapping_code_fence(markdown_text)

    assert unwrapped_text == markdown_text


def test_strip_wrapping_code_fence_fence_inside_larger_document_returns_unchanged() -> None:
    markdown_text = "# Title\n\n```python\nprint('hi')\n```\n\nMore text."

    unwrapped_text = MarkdownUtils.strip_wrapping_code_fence(markdown_text)

    assert unwrapped_text == markdown_text


def test_strip_wrapping_code_fence_no_fence_returns_unchanged() -> None:
    markdown_text = "# Title\n\nJust text."

    unwrapped_text = MarkdownUtils.strip_wrapping_code_fence(markdown_text)

    assert unwrapped_text == markdown_text


def test_strip_wrapping_code_fence_strips_surrounding_whitespace_before_checking() -> None:
    markdown_text = "  \n```markdown\n# Title\n\nBody.\n```\n  "

    unwrapped_text = MarkdownUtils.strip_wrapping_code_fence(markdown_text)

    assert unwrapped_text == "# Title\n\nBody.\n"


def test_find_title_leading_h1_returns_text() -> None:
    markdown_text = "# Sourdough Starters\n\nBody text."

    title_text = MarkdownUtils.find_title(markdown_text)

    assert title_text == "Sourdough Starters"


def test_find_title_leading_h2_returns_none() -> None:
    markdown_text = "## Not The Title\n\nBody text."

    title_text = MarkdownUtils.find_title(markdown_text)

    assert title_text is None


def test_find_title_paragraph_first_returns_none() -> None:
    markdown_text = "Some preamble.\n\n# Title\n\nBody text."

    title_text = MarkdownUtils.find_title(markdown_text)

    assert title_text is None


def test_find_title_empty_heading_returns_none() -> None:
    markdown_text = "# \n\nBody text."

    title_text = MarkdownUtils.find_title(markdown_text)

    assert title_text is None


def test_find_heading_levels_returns_every_heading_level_in_order() -> None:
    markdown_text = "# Title\n\n## Section\n\n### Sub\n\n## Section Two"

    heading_levels = MarkdownUtils.find_heading_levels(markdown_text)

    assert heading_levels == [1, 2, 3, 2]


def test_has_raw_html_block_html_returns_true() -> None:
    markdown_text = "<div>Hello</div>\n\n# Title"

    assert MarkdownUtils.has_raw_html(markdown_text) is True


def test_has_raw_html_inline_html_returns_true() -> None:
    markdown_text = "# Title\n\nSome text with <span>inline</span> html."

    assert MarkdownUtils.has_raw_html(markdown_text) is True


def test_has_raw_html_no_html_returns_false() -> None:
    markdown_text = "# Title\n\nJust plain text."

    assert MarkdownUtils.has_raw_html(markdown_text) is False


def test_has_image_with_image_returns_true() -> None:
    markdown_text = "# Title\n\n![alt](http://example.com/photo.png)"

    assert MarkdownUtils.has_image(markdown_text) is True


def test_has_image_without_image_returns_false() -> None:
    markdown_text = "# Title\n\nJust plain text."

    assert MarkdownUtils.has_image(markdown_text) is False


def test_find_first_block_type_returns_first_token_type() -> None:
    markdown_text = "# Title\n\nBody text."

    first_block_type = MarkdownUtils.find_first_block_type(markdown_text)

    assert first_block_type == "heading_open"


def test_find_first_block_type_empty_document_returns_none() -> None:
    first_block_type = MarkdownUtils.find_first_block_type("")

    assert first_block_type is None
