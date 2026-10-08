from libs.generate_text.graphs.blog_post.blog_post_body_output_format import (
    BLOG_POST_BODY_FORMAT_RULES,
    EMPTY_BODY_MESSAGE,
    HEADING_TOO_DEEP_MESSAGE,
    IMAGE_MESSAGE,
    MULTIPLE_H1_MESSAGE,
    NO_LEADING_TITLE_MESSAGE,
    RAW_HTML_MESSAGE,
    SKIPPED_HEADING_LEVEL_MESSAGE,
    BlogPostBodyOutputFormat,
)
from libs.generate_text.results import ValidateOutputResult

VALID_BODY_TEXT = (
    "# Sourdough Starters\n\n## Feeding\n\nFeed it daily.\n\n### Hydration\n\nUse equal parts."
)


def test_normalize_output_strips_wrapping_fence_and_trims_whitespace() -> None:
    output_text = f"  \n```markdown\n{VALID_BODY_TEXT}\n```\n  "

    normalized_text = BlogPostBodyOutputFormat().normalize_output(output_text)

    assert normalized_text == VALID_BODY_TEXT


def test_normalize_output_keeps_inner_code_block() -> None:
    output_text = "# Title\n\n```python\nprint('hi')\n```\n\nMore text."

    normalized_text = BlogPostBodyOutputFormat().normalize_output(output_text)

    assert normalized_text == output_text


def test_validate_output_valid_document_returns_no_errors() -> None:
    validate_output_result = BlogPostBodyOutputFormat().validate_output(VALID_BODY_TEXT)

    assert validate_output_result == ValidateOutputResult(error_messages=[])


def test_validate_output_preamble_before_title_reports_no_leading_title() -> None:
    output_text = "Here is the post:\n\n# Title\n\nBody."

    validate_output_result = BlogPostBodyOutputFormat().validate_output(output_text)

    assert NO_LEADING_TITLE_MESSAGE in validate_output_result.error_messages


def test_validate_output_no_title_reports_no_leading_title() -> None:
    output_text = "## Section\n\nBody."

    validate_output_result = BlogPostBodyOutputFormat().validate_output(output_text)

    assert NO_LEADING_TITLE_MESSAGE in validate_output_result.error_messages


def test_validate_output_empty_title_reports_no_leading_title() -> None:
    output_text = "# \n\nBody."

    validate_output_result = BlogPostBodyOutputFormat().validate_output(output_text)

    assert NO_LEADING_TITLE_MESSAGE in validate_output_result.error_messages


def test_validate_output_two_h1_headings_reports_multiple_h1() -> None:
    output_text = "# Title\n\nBody.\n\n# Another Title\n\nMore body."

    validate_output_result = BlogPostBodyOutputFormat().validate_output(output_text)

    assert MULTIPLE_H1_MESSAGE in validate_output_result.error_messages


def test_validate_output_raw_html_reports_raw_html_message() -> None:
    output_text = "# Title\n\nSome text with <span>inline</span> html."

    validate_output_result = BlogPostBodyOutputFormat().validate_output(output_text)

    assert RAW_HTML_MESSAGE in validate_output_result.error_messages


def test_validate_output_image_reports_image_message() -> None:
    output_text = "# Title\n\n![alt](http://example.com/photo.png)"

    validate_output_result = BlogPostBodyOutputFormat().validate_output(output_text)

    assert IMAGE_MESSAGE in validate_output_result.error_messages


def test_validate_output_heading_too_deep_reports_heading_too_deep() -> None:
    output_text = "# Title\n\n## Section\n\n#### Too Deep"

    validate_output_result = BlogPostBodyOutputFormat().validate_output(output_text)

    assert HEADING_TOO_DEEP_MESSAGE in validate_output_result.error_messages


def test_validate_output_skipped_heading_level_reports_skipped_heading_level() -> None:
    output_text = "# Title\n\n### Skipped"

    validate_output_result = BlogPostBodyOutputFormat().validate_output(output_text)

    assert SKIPPED_HEADING_LEVEL_MESSAGE in validate_output_result.error_messages


def test_validate_output_h2_then_h3_then_h2_has_no_skipped_heading_level() -> None:
    output_text = "# Title\n\n## Section\n\n### Sub\n\n## Section Two"

    validate_output_result = BlogPostBodyOutputFormat().validate_output(output_text)

    assert SKIPPED_HEADING_LEVEL_MESSAGE not in validate_output_result.error_messages


def test_validate_output_with_subtitle_returns_no_errors() -> None:
    output_text = "# Title\n\n*A one-line subtitle.*\n\n## Section\n\nBody."

    validate_output_result = BlogPostBodyOutputFormat().validate_output(output_text)

    assert validate_output_result == ValidateOutputResult(error_messages=[])


def test_validate_output_title_only_reports_empty_body() -> None:
    output_text = "# Title"

    validate_output_result = BlogPostBodyOutputFormat().validate_output(output_text)

    assert validate_output_result == ValidateOutputResult(error_messages=[EMPTY_BODY_MESSAGE])


def test_validate_output_title_and_subtitle_with_nothing_after_reports_empty_body() -> None:
    output_text = "# Title\n\n*A one-line subtitle.*"

    validate_output_result = BlogPostBodyOutputFormat().validate_output(output_text)

    assert validate_output_result == ValidateOutputResult(error_messages=[EMPTY_BODY_MESSAGE])


def test_blog_post_body_format_rules_mentions_optional_italic_subtitle() -> None:
    assert "optional one-line subtitle" in BLOG_POST_BODY_FORMAT_RULES
