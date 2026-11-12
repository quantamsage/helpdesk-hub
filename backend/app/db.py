"""Database connection pool and the per-request connection dependency."""
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def create_pool(database_url: str) -> ConnectionPool:
    return ConnectionPool(
        database_url,
        min_size=1,
        max_size=5,  # Supabase's pooler has a small connection limit on the free tier
        kwargs={"row_factory": dict_row},  # rows come back as dicts
        check=ConnectionPool.check_connection,  # replace connections the server dropped
        open=True,
    )


def get_conn(request: Request) -> Iterator[Connection]:
    """One connection (and one transaction) per request.

    Leaving the block normally COMMITs. If the route raises an error,
    the transaction is ROLLED BACK, so a request never half-saves.
    """
    pool: ConnectionPool = request.app.state.pool
    with pool.connection() as conn:
        yield conn


# scope="function": commit BEFORE the response is sent. With the default
# ("request") the commit would happen afterwards, so a failed commit could
# still have told the client "success".
DbConn = Annotated[Connection, Depends(get_conn, scope="function")]
