# Matches the names Postgres generates, so Orm metadata and hand-written SQL agree.
NAMING_CONVENTION = {
    "pk": "%(table_name)s_pkey",
    "uq": "%(table_name)s_%(column_0_N_name)s_key",
    "ix": "%(table_name)s_%(column_0_N_name)s_idx",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "ck": "%(table_name)s_%(constraint_name)s_check",
}
UTC_NOW_SQL = "(now() AT TIME ZONE 'utc')"
