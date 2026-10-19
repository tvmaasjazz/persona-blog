from itertools import pairwise

from libs.core.utils.markdown_utils import MarkdownUtils
from libs.generate_text.output_formats import BaseGenerateTextOutputFormat
from libs.generate_text.results import ValidateOutputResult

BLOG_POST_BODY_FORMAT_RULES = (
    "Write the post body in Markdown. Start with a single `# Title` line and nothing "
    "before it: no preamble, no restated instructions. Use exactly one H1, the title. "
    "An optional one-line subtitle may follow the title as a single italic line, e.g. "
    "`*A one-line subtitle.*`, and nothing else goes between the title and the body. "
    "Below it, use `##` and `###` headings only, and never skip a level (an H1 is "
    "followed by `##`, never straight to `###`). Paragraphs, bold and italic, lists, "
    "blockquotes, links, and code are all fine. Never use raw HTML, and never include "
    "images."
)

MAX_HEADING_LEVEL = 3

NO_LEADING_TITLE_MESSAGE = (
    "The document must start with a single '# Title' heading, with nothing before it."
)
MULTIPLE_H1_MESSAGE = "The document must have exactly one H1 heading."
EMPTY_BODY_MESSAGE = "The post must have a body after the title and subtitle."
RAW_HTML_MESSAGE = "The document must not contain raw HTML."
IMAGE_MESSAGE = "The document must not contain images."
HEADING_TOO_DEEP_MESSAGE = "Headings below the title must be '##' or '###', never deeper."
SKIPPED_HEADING_LEVEL_MESSAGE = (
    "Headings below the title must not skip a level (an H1 must be followed by an H2, never an H3)."
)


class BlogPostBodyOutputFormat(BaseGenerateTextOutputFormat):
    """The Markdown shape a blog post body must follow."""

    def normalize_output(self, output_text: str) -> str:
        """Strips a code fence wrapping the whole output, then surrounding whitespace."""
        unfenced_text = MarkdownUtils.strip_wrapping_code_fence(output_text)
        return unfenced_text.strip()

    def validate_output(self, output_text: str) -> ValidateOutputResult:
        """Lists every rule the post breaks, with an empty list when it follows them all."""
        error_messages: list[str] = []

        split_markdown_post_result = MarkdownUtils.split_post(output_text)
        if split_markdown_post_result.title is None:
            error_messages.append(NO_LEADING_TITLE_MESSAGE)
        elif not split_markdown_post_result.body:
            error_messages.append(EMPTY_BODY_MESSAGE)

        heading_levels = MarkdownUtils.find_heading_levels(output_text)
        if heading_levels.count(1) != 1:
            error_messages.append(MULTIPLE_H1_MESSAGE)

        if MarkdownUtils.has_raw_html(output_text):
            error_messages.append(RAW_HTML_MESSAGE)

        if MarkdownUtils.has_image(output_text):
            error_messages.append(IMAGE_MESSAGE)

        if any(heading_level > MAX_HEADING_LEVEL for heading_level in heading_levels):
            error_messages.append(HEADING_TOO_DEEP_MESSAGE)

        if self._has_skipped_heading_level(heading_levels):
            error_messages.append(SKIPPED_HEADING_LEVEL_MESSAGE)

        return ValidateOutputResult(error_messages=error_messages)

    @staticmethod
    def _has_skipped_heading_level(heading_levels: list[int]) -> bool:
        for previous_level, next_level in pairwise(heading_levels):
            if next_level > previous_level + 1:
                return True
        return False
