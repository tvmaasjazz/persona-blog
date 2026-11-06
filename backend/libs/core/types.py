from enum import StrEnum


class SortDirectionType(StrEnum):
    ASC = "ASC"
    DESC = "DESC"


class FilterOperatorType(StrEnum):
    EQUALS = "EQUALS"
    IN = "IN"
    GTE = "GTE"
    LT = "LT"
    HAS_VALUE = "HAS_VALUE"
