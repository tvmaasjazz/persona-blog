from libs.core.utils.markdown_utils import MarkdownUtils

# The body follows the post's title, which is an H1 stored on its own column.
TITLE_HEADING_LEVEL = 1
ALLOWED_BODY_HEADING_LEVELS = (2, 3)

H1_IN_BODY_PROBLEM = "The body must not contain an H1 heading"
HEADING_LEVEL_NOT_ALLOWED_PROBLEM = "The body may only use H2 and H3 headings"
SKIPPED_HEADING_LEVEL_PROBLEM_TEMPLATE = (
    "Heading level jumps from H{previous_level} to H{heading_level} without an "
    "H{expected_level} first"
)
RAW_HTML_PROBLEM = "The body must not contain raw HTML"
IMAGE_PROBLEM = "The body must not contain images"


class BlogPostValidationUtils:
    """Pure checks of a blog post's Markdown body against the allowed structure."""

    @staticmethod
    def find_body_problems(body: str) -> list[str]:
        """Every rule the body breaks, as readable messages; empty when the body is valid."""
        problems: list[str] = []
        heading_levels = MarkdownUtils.find_heading_levels(body)

        if TITLE_HEADING_LEVEL in heading_levels:
            problems.append(H1_IN_BODY_PROBLEM)
        if any(level not in ALLOWED_BODY_HEADING_LEVELS for level in heading_levels):
            problems.append(HEADING_LEVEL_NOT_ALLOWED_PROBLEM)
        problems.extend(BlogPostValidationUtils._find_skipped_heading_levels(heading_levels))

        if MarkdownUtils.has_raw_html(body):
            problems.append(RAW_HTML_PROBLEM)
        if MarkdownUtils.has_image(body):
            problems.append(IMAGE_PROBLEM)
        return problems

    @staticmethod
    def _find_skipped_heading_levels(heading_levels: list[int]) -> list[str]:
        problems: list[str] = []
        previous_level = TITLE_HEADING_LEVEL
        for heading_level in heading_levels:
            if heading_level > previous_level + 1:
                problems.append(
                    SKIPPED_HEADING_LEVEL_PROBLEM_TEMPLATE.format(
                        previous_level=previous_level,
                        heading_level=heading_level,
                        expected_level=previous_level + 1,
                    )
                )
            previous_level = heading_level
        return problems
