from libs.blog_posts.utils.blog_post_validation_utils import (
    H1_IN_BODY_PROBLEM,
    HEADING_LEVEL_NOT_ALLOWED_PROBLEM,
    IMAGE_PROBLEM,
    RAW_HTML_PROBLEM,
    SKIPPED_HEADING_LEVEL_PROBLEM_TEMPLATE,
    BlogPostValidationUtils,
)


def test_find_body_problems_paragraph_then_h2_h3_h2_returns_no_problems() -> None:
    body = (
        "A paragraph that opens the post.\n\n## A Section\n\n### A Subsection\n\n## Another Section"
    )

    body_problems = BlogPostValidationUtils.find_body_problems(body)

    assert body_problems == []


def test_find_body_problems_opening_at_h3_returns_skipped_heading_level_problem() -> None:
    body = "### Opens Too Deep\n\nA paragraph."

    body_problems = BlogPostValidationUtils.find_body_problems(body)

    assert body_problems == [
        SKIPPED_HEADING_LEVEL_PROBLEM_TEMPLATE.format(
            previous_level=1, heading_level=3, expected_level=2
        )
    ]


def test_find_body_problems_opening_at_h4_returns_not_allowed_and_skipped_problems() -> None:
    body = "#### Opens Too Deep\n\nA paragraph."

    body_problems = BlogPostValidationUtils.find_body_problems(body)

    assert body_problems == [
        HEADING_LEVEL_NOT_ALLOWED_PROBLEM,
        SKIPPED_HEADING_LEVEL_PROBLEM_TEMPLATE.format(
            previous_level=1, heading_level=4, expected_level=2
        ),
    ]


def test_find_body_problems_h1_returns_h1_and_not_allowed_problems() -> None:
    body = "# Not Allowed Here\n\nA paragraph."

    body_problems = BlogPostValidationUtils.find_body_problems(body)

    assert body_problems == [H1_IN_BODY_PROBLEM, HEADING_LEVEL_NOT_ALLOWED_PROBLEM]


def test_find_body_problems_raw_html_block_returns_raw_html_problem() -> None:
    body = "<div>Hello</div>\n\n## A Section"

    body_problems = BlogPostValidationUtils.find_body_problems(body)

    assert body_problems == [RAW_HTML_PROBLEM]


def test_find_body_problems_raw_html_inline_returns_raw_html_problem() -> None:
    body = "## A Section\n\nSome text with <span>inline</span> html."

    body_problems = BlogPostValidationUtils.find_body_problems(body)

    assert body_problems == [RAW_HTML_PROBLEM]


def test_find_body_problems_image_returns_image_problem() -> None:
    body = "## A Section\n\n![alt](http://example.com/photo.png)"

    body_problems = BlogPostValidationUtils.find_body_problems(body)

    assert body_problems == [IMAGE_PROBLEM]


def test_find_body_problems_several_problems_returns_all_of_them() -> None:
    body = "# Not Allowed\n\n<div>Hello</div>\n\n![alt](http://example.com/a.png)"

    body_problems = BlogPostValidationUtils.find_body_problems(body)

    assert body_problems == [
        H1_IN_BODY_PROBLEM,
        HEADING_LEVEL_NOT_ALLOWED_PROBLEM,
        RAW_HTML_PROBLEM,
        IMAGE_PROBLEM,
    ]
