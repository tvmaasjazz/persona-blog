import pytest

from libs.core.results import SplitMarkdownPostResult
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


def test_split_post_title_subtitle_and_body_returns_each_part() -> None:
    markdown_text = "# Sourdough Starters\n\n*A one-line subtitle.*\n\n## Feeding\n\nFeed it daily."

    split_markdown_post_result = MarkdownUtils.split_post(markdown_text)

    assert split_markdown_post_result == SplitMarkdownPostResult(
        title="Sourdough Starters",
        subtitle="A one-line subtitle.",
        body="## Feeding\n\nFeed it daily.",
    )


def test_split_post_subtitle_on_next_line_returns_subtitle() -> None:
    markdown_text = "# Sourdough Starters\n*A one-line subtitle.*\n\nBody paragraph."

    split_markdown_post_result = MarkdownUtils.split_post(markdown_text)

    assert split_markdown_post_result == SplitMarkdownPostResult(
        title="Sourdough Starters",
        subtitle="A one-line subtitle.",
        body="Body paragraph.",
    )


def test_split_post_subtitle_after_blank_line_returns_subtitle() -> None:
    markdown_text = "# Sourdough Starters\n\n*A one-line subtitle.*\n\nBody paragraph."

    split_markdown_post_result = MarkdownUtils.split_post(markdown_text)

    assert split_markdown_post_result == SplitMarkdownPostResult(
        title="Sourdough Starters",
        subtitle="A one-line subtitle.",
        body="Body paragraph.",
    )


def test_split_post_underscore_italics_returns_subtitle() -> None:
    markdown_text = "# Sourdough Starters\n\n_A one-line subtitle._\n\nBody paragraph."

    split_markdown_post_result = MarkdownUtils.split_post(markdown_text)

    assert split_markdown_post_result == SplitMarkdownPostResult(
        title="Sourdough Starters",
        subtitle="A one-line subtitle.",
        body="Body paragraph.",
    )


def test_split_post_no_subtitle_returns_subtitle_none() -> None:
    markdown_text = "# Sourdough Starters\n\nJust a paragraph, no subtitle.\n\n## Section"

    split_markdown_post_result = MarkdownUtils.split_post(markdown_text)

    assert split_markdown_post_result == SplitMarkdownPostResult(
        title="Sourdough Starters",
        subtitle=None,
        body="Just a paragraph, no subtitle.\n\n## Section",
    )


def test_split_post_paragraph_only_partly_italic_stays_in_body() -> None:
    markdown_text = "# Sourdough Starters\n\n*Partly* italic and more text.\n\nBody paragraph."

    split_markdown_post_result = MarkdownUtils.split_post(markdown_text)

    assert split_markdown_post_result == SplitMarkdownPostResult(
        title="Sourdough Starters",
        subtitle=None,
        body="*Partly* italic and more text.\n\nBody paragraph.",
    )


def test_split_post_bold_only_line_stays_in_body() -> None:
    markdown_text = "# Sourdough Starters\n\n**Bold only.**\n\nBody paragraph."

    split_markdown_post_result = MarkdownUtils.split_post(markdown_text)

    assert split_markdown_post_result == SplitMarkdownPostResult(
        title="Sourdough Starters",
        subtitle=None,
        body="**Bold only.**\n\nBody paragraph.",
    )


def test_split_post_no_leading_h1_returns_title_and_subtitle_none_and_body_whole_text() -> None:
    markdown_text = "## Section\n\nJust text, no title."

    split_markdown_post_result = MarkdownUtils.split_post(markdown_text)

    assert split_markdown_post_result == SplitMarkdownPostResult(
        title=None, subtitle=None, body="## Section\n\nJust text, no title."
    )


def test_split_post_title_only_returns_empty_body() -> None:
    markdown_text = "# Sourdough Starters"

    split_markdown_post_result = MarkdownUtils.split_post(markdown_text)

    assert split_markdown_post_result == SplitMarkdownPostResult(
        title="Sourdough Starters", subtitle=None, body=""
    )


def test_split_post_body_markdown_untouched() -> None:
    markdown_text = (
        "# Sourdough Starters\n\nBody has **bold** text and a [link](http://example.com) in it."
    )

    split_markdown_post_result = MarkdownUtils.split_post(markdown_text)

    assert split_markdown_post_result == SplitMarkdownPostResult(
        title="Sourdough Starters",
        subtitle=None,
        body="Body has **bold** text and a [link](http://example.com) in it.",
    )
