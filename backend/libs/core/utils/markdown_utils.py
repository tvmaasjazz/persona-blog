from markdown_it import MarkdownIt
from markdown_it.token import Token

ALLOWED_FENCE_INFO_STRINGS = ("", "markdown", "md")


class MarkdownUtils:
    @staticmethod
    def strip_wrapping_code_fence(markdown_text: str) -> str:
        """Unwraps a document that is nothing but one fenced code block, the way a model
        sometimes wraps Markdown in a ```markdown fence. A fence inside a larger document
        is left alone."""
        trimmed_text = markdown_text.strip()
        tokens = MarkdownUtils._parse(trimmed_text)
        if len(tokens) != 1 or tokens[0].type != "fence":
            return markdown_text

        fence_token = tokens[0]
        info_string = fence_token.info.strip().lower()
        if info_string not in ALLOWED_FENCE_INFO_STRINGS:
            return markdown_text

        return fence_token.content

    @staticmethod
    def find_title(markdown_text: str) -> str | None:
        tokens = MarkdownUtils._parse(markdown_text)
        first_heading_level = MarkdownUtils._find_first_block_heading_level(tokens)
        if first_heading_level != 1:
            return None
        title_text = MarkdownUtils._find_heading_inline_text(tokens, index=0)
        if title_text is None or not title_text.strip():
            return None
        return title_text.strip()

    @staticmethod
    def find_heading_levels(markdown_text: str) -> list[int]:
        tokens = MarkdownUtils._parse(markdown_text)
        return [int(token.tag[1:]) for token in tokens if token.type == "heading_open"]

    @staticmethod
    def has_raw_html(markdown_text: str) -> bool:
        """Inline HTML sits among an inline token's children, not at the top level."""
        token_types = MarkdownUtils._find_all_token_types(markdown_text)
        return "html_block" in token_types or "html_inline" in token_types

    @staticmethod
    def has_image(markdown_text: str) -> bool:
        token_types = MarkdownUtils._find_all_token_types(markdown_text)
        return "image" in token_types

    @staticmethod
    def find_first_block_type(markdown_text: str) -> str | None:
        tokens = MarkdownUtils._parse(markdown_text)
        if not tokens:
            return None
        return tokens[0].type

    @staticmethod
    def _find_first_block_heading_level(tokens: list[Token]) -> int | None:
        if not tokens or tokens[0].type != "heading_open":
            return None
        return int(tokens[0].tag[1:])

    @staticmethod
    def _find_heading_inline_text(tokens: list[Token], index: int) -> str | None:
        inline_token = tokens[index + 1]
        if inline_token.type != "inline":
            return None
        return inline_token.content

    @staticmethod
    def _find_all_token_types(markdown_text: str) -> set[str]:
        tokens = MarkdownUtils._parse(markdown_text)
        token_types = {token.type for token in tokens}
        for token in tokens:
            child_tokens = token.children or []
            token_types.update(child_token.type for child_token in child_tokens)
        return token_types

    @staticmethod
    def _parse(markdown_text: str) -> list[Token]:
        markdown_parser = MarkdownIt("commonmark", {"html": True})
        return markdown_parser.parse(markdown_text)
