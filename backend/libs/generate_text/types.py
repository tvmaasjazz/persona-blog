from enum import StrEnum


class TextType(StrEnum):
    BLOG_POST = "BLOG_POST"


class GenerateTextStatusType(StrEnum):
    AWAITING_REVIEW = "AWAITING_REVIEW"
    COMPLETED = "COMPLETED"
