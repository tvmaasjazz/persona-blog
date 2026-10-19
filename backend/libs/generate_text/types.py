from enum import StrEnum


class TextType(StrEnum):
    BLOG_POST = "BLOG_POST"


class GenerateTextNodeType(StrEnum):
    """The graph's nodes, shared by every text type."""

    GENERATE_OUTLINE = "GENERATE_OUTLINE"
    REWRITE_OUTLINE = "REWRITE_OUTLINE"
    REVIEW_OUTLINE = "REVIEW_OUTLINE"
    GENERATE_DRAFT = "GENERATE_DRAFT"
    REWRITE_DRAFT = "REWRITE_DRAFT"
    REVIEW_DRAFT = "REVIEW_DRAFT"
    HUMANIZE = "HUMANIZE"
    REWRITE_HUMANIZE = "REWRITE_HUMANIZE"
    REVIEW_HUMANIZE = "REVIEW_HUMANIZE"


class GenerateTextRunStatusType(StrEnum):
    """Where a run is. AWAITING_REVIEW means a review node is holding it."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class GenerateTextStepStatusType(StrEnum):
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    AWAITING_REVIEW = "AWAITING_REVIEW"


class HumanDecisionType(StrEnum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
