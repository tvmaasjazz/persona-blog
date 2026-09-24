from enum import StrEnum


class TextType(StrEnum):
    BLOG_POST = "BLOG_POST"


class GenerateTextStatusType(StrEnum):
    AWAITING_REVIEW = "AWAITING_REVIEW"
    COMPLETED = "COMPLETED"


class GenerateTextNodeType(StrEnum):
    """The graph's nodes. LangGraph takes the member itself as the node name."""

    WRITE_BLOG_POST = "WRITE_BLOG_POST"
    REVIEW_BLOG_POST = "REVIEW_BLOG_POST"
    REWRITE_BLOG_POST = "REWRITE_BLOG_POST"
