"""Reads Markdown through markdown-it, which parses a document into a flat list of tokens
rather than a tree.

Each top-level block becomes a run of tokens: a heading is `heading_open` (its `tag` is
"h1".."h6"), then an `inline` token holding the heading's text, then `heading_close`. A
paragraph is `paragraph_open`, `inline`, `paragraph_close`. Anything inside a line of
text, such as an image or a `<span>`, is not in that list at all: it sits among the
`inline` token's `children`. A fenced code block is a single `fence` token whose `info` is
the language after the opening backticks and whose `content` is the code inside.
"""

from markdown_it import MarkdownIt
from markdown_it.token import Token

FENCE_TOKEN_TYPE = "fence"
HEADING_OPEN_TOKEN_TYPE = "heading_open"
INLINE_TOKEN_TYPE = "inline"
HTML_TOKEN_TYPES = ("html_block", "html_inline")
IMAGE_TOKEN_TYPE = "image"

TITLE_HEADING_LEVEL = 1
ALLOWED_FENCE_INFO_STRINGS = ("", "markdown", "md")


class MarkdownUtils:
    @staticmethod
    def strip_wrapping_code_fence(markdown_text: str) -> str:
        """Unwraps a document that is nothing but one fenced code block, the way a model
        sometimes wraps Markdown in a ```markdown fence. A fence inside a larger document
        is left alone."""
        trimmed_text = markdown_text.strip()
        tokens = MarkdownUtils._parse(trimmed_text)
        if len(tokens) != 1 or tokens[0].type != FENCE_TOKEN_TYPE:
            return markdown_text

        fence_token = tokens[0]
        info_string = fence_token.info.strip().lower()
        if info_string not in ALLOWED_FENCE_INFO_STRINGS:
            return markdown_text

        return fence_token.content

    @staticmethod
    def find_title(markdown_text: str) -> str | None:
        """The text of the H1 the document opens with. None when it opens with anything
        else, or the H1 is empty."""
        tokens = MarkdownUtils._parse(markdown_text)
        if not tokens or tokens[0].type != HEADING_OPEN_TOKEN_TYPE:
            return None
        if MarkdownUtils._find_heading_level(tokens[0]) != TITLE_HEADING_LEVEL:
            return None

        # The heading's text is in the inline token right after heading_open.
        title_token = tokens[1]
        title_text = title_token.content.strip()
        return title_text or None

    @staticmethod
    def find_heading_levels(markdown_text: str) -> list[int]:
        tokens = MarkdownUtils._parse(markdown_text)
        return [
            MarkdownUtils._find_heading_level(token)
            for token in tokens
            if token.type == HEADING_OPEN_TOKEN_TYPE
        ]

    @staticmethod
    def has_raw_html(markdown_text: str) -> bool:
        token_types = MarkdownUtils._find_all_token_types(markdown_text)
        return any(html_token_type in token_types for html_token_type in HTML_TOKEN_TYPES)

    @staticmethod
    def has_image(markdown_text: str) -> bool:
        token_types = MarkdownUtils._find_all_token_types(markdown_text)
        return IMAGE_TOKEN_TYPE in token_types

    @staticmethod
    def _find_heading_level(heading_open_token: Token) -> int:
        # The tag is "h1".."h6"; the digit is the level.
        return int(heading_open_token.tag[1:])

    @staticmethod
    def _find_all_token_types(markdown_text: str) -> set[str]:
        """Includes the children of inline tokens, where images and inline HTML live."""
        tokens = MarkdownUtils._parse(markdown_text)
        token_types = {token.type for token in tokens}
        for token in tokens:
            if token.type == INLINE_TOKEN_TYPE and token.children:
                token_types.update(child_token.type for child_token in token.children)
        return token_types

    @staticmethod
    def _parse(markdown_text: str) -> list[Token]:
        # html on, so raw HTML parses into html_block / html_inline tokens to be caught,
        # rather than being treated as text.
        markdown_parser = MarkdownIt("commonmark", {"html": True})
        return markdown_parser.parse(markdown_text)
