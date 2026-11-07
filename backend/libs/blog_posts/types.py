from enum import StrEnum


class UserBlogPostSortType(StrEnum):
    CREATED_AT = "CREATED_AT"
    PUBLISHED_AT = "PUBLISHED_AT"
    TITLE = "TITLE"


class PublicBlogPostSortType(StrEnum):
    FEED_SCORE = "FEED_SCORE"
    PUBLISHED_AT = "PUBLISHED_AT"
    TITLE = "TITLE"
