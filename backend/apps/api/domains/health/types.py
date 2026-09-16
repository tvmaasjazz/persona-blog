from enum import StrEnum


class HealthStatusType(StrEnum):
    OK = "OK"
    DEGRADED = "DEGRADED"


class DependencyStatusType(StrEnum):
    REACHABLE = "REACHABLE"
    UNREACHABLE = "UNREACHABLE"
