from enum import StrEnum


class PublicBlogPostSortType(StrEnum):
    FEED_SCORE = "FEED_SCORE"
    PUBLISHED_AT = "PUBLISHED_AT"
    TITLE = "TITLE"
