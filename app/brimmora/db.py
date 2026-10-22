from contextlib import contextmanager

import psycopg

from .config import settings


def admin():
    """Platform connection: identity lookups, quarantine, audit log."""
    return psycopg.connect(settings.pg_admin_dsn, autocommit=True)


@contextmanager
def as_user(groups):
    """Connection as app_user with the caller's groups set for row-level security.

    set_config(..., true) scopes the setting to this transaction, so it can
    never leak to another request.
    """
    with psycopg.connect(settings.pg_app_dsn) as conn:
        conn.execute("SELECT set_config('app.groups', %s, true)", (",".join(groups),))
        yield conn
