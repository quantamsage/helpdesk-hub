"""All SQL lives here. Every value is passed as a parameter (%(name)s),
never pasted into the SQL string, so user input can't change a query."""
from uuid import UUID

from psycopg import Connection

# A fixed column list (never user input), reused in several queries below.
USER_COLUMNS = "id, email, name, role, created_at"

TICKET_SELECT = """
    SELECT t.id, t.title, t.description, t.status, t.created_at, t.updated_at,
           t.customer_id, c.name AS customer_name,
           t.assignee_id, a.name AS assignee_name
    FROM support_tickets t
    JOIN support_users c ON c.id = t.customer_id
    LEFT JOIN support_users a ON a.id = t.assignee_id
"""

COMMENT_SELECT = """
    SELECT cm.id, cm.ticket_id, cm.body, cm.created_at,
           u.id AS author_id, u.name AS author_name, u.role AS author_role
    FROM support_comments cm
    JOIN support_users u ON u.id = cm.author_id
"""


# ---- Users ------------------------------------------------------------------

def create_customer(conn: Connection, email: str, name: str, password_hash: str) -> dict:
    """Raises psycopg.errors.UniqueViolation if the email is taken.
    No role column here: the database role isn't allowed to set it."""
    return conn.execute(
        f"""INSERT INTO support_users (email, name, password_hash)
            VALUES (%(email)s, %(name)s, %(password_hash)s)
            RETURNING {USER_COLUMNS}""",
        {"email": email, "name": name, "password_hash": password_hash},
    ).fetchone()


def get_user_by_id(conn: Connection, user_id: UUID) -> dict | None:
    return conn.execute(
        f"SELECT {USER_COLUMNS} FROM support_users WHERE id = %(id)s", {"id": user_id}
    ).fetchone()


def get_login_details(conn: Connection, email: str) -> dict | None:
    return conn.execute(
        "SELECT id, password_hash FROM support_users WHERE email = %(email)s", {"email": email}
    ).fetchone()


def list_staff(conn: Connection) -> list[dict]:
    return conn.execute(
        "SELECT id, name FROM support_users WHERE role = 'staff' ORDER BY name"
    ).fetchall()


def is_staff(conn: Connection, user_id: UUID) -> bool:
    row = conn.execute(
        "SELECT 1 FROM support_users WHERE id = %(id)s AND role = 'staff'", {"id": user_id}
    ).fetchone()
    return row is not None


# ---- Tickets ----------------------------------------------------------------

def create_ticket(conn: Connection, customer_id: UUID, title: str, description: str) -> dict:
    row = conn.execute(
        """INSERT INTO support_tickets (customer_id, title, description)
           VALUES (%(customer_id)s, %(title)s, %(description)s)
           RETURNING id""",
        {"customer_id": customer_id, "title": title, "description": description},
    ).fetchone()
    return get_ticket(conn, row["id"])


def get_ticket(conn: Connection, ticket_id: UUID) -> dict | None:
    return conn.execute(TICKET_SELECT + " WHERE t.id = %(id)s", {"id": ticket_id}).fetchone()


def list_tickets(
    conn: Connection,
    *,
    customer_id: UUID | None,
    status: str | None,
    assignee: UUID | str | None,  # a staff id, "none", or None for no filter
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    """Returns (one page of tickets, total matching).

    The WHERE clause is built only from the fixed strings below;
    the values themselves always go in `params`."""
    conditions = []
    params: dict = {"limit": limit, "offset": offset}
    if customer_id is not None:
        conditions.append("t.customer_id = %(customer_id)s")
        params["customer_id"] = customer_id
    if status is not None:
        conditions.append("t.status = %(status)s")
        params["status"] = status
    if assignee == "none":
        conditions.append("t.assignee_id IS NULL")
    elif assignee is not None:
        conditions.append("t.assignee_id = %(assignee_id)s")
        params["assignee_id"] = assignee
    where = " WHERE " + " AND ".join(conditions) if conditions else ""

    total = conn.execute("SELECT count(*) AS n FROM support_tickets t" + where, params).fetchone()["n"]
    rows = conn.execute(
        TICKET_SELECT + where + " ORDER BY t.created_at DESC, t.id DESC LIMIT %(limit)s OFFSET %(offset)s",
        params,
    ).fetchall()
    return rows, total


def update_ticket(
    conn: Connection, ticket_id: UUID, *, status: str | None, change_assignee: bool, assignee_id: UUID | None
) -> dict:
    """status=None keeps the current status. change_assignee=False keeps the
    current assignee (so we can tell "not sent" apart from "set to null")."""
    conn.execute(
        """UPDATE support_tickets
           SET status = COALESCE(%(status)s, status),
               assignee_id = CASE WHEN %(change_assignee)s THEN %(assignee_id)s::uuid ELSE assignee_id END,
               updated_at = now()
           WHERE id = %(id)s""",
        {"id": ticket_id, "status": status, "change_assignee": change_assignee, "assignee_id": assignee_id},
    )
    return get_ticket(conn, ticket_id)


def touch_ticket(conn: Connection, ticket_id: UUID) -> None:
    """Bump updated_at, e.g. when someone comments."""
    conn.execute("UPDATE support_tickets SET updated_at = now() WHERE id = %(id)s", {"id": ticket_id})


# ---- Comments ---------------------------------------------------------------

def list_comments(conn: Connection, ticket_id: UUID) -> list[dict]:
    return conn.execute(
        COMMENT_SELECT + " WHERE cm.ticket_id = %(ticket_id)s ORDER BY cm.created_at, cm.id",
        {"ticket_id": ticket_id},
    ).fetchall()


def create_comment(conn: Connection, ticket_id: UUID, author_id: UUID, body: str) -> dict:
    row = conn.execute(
        """INSERT INTO support_comments (ticket_id, author_id, body)
           VALUES (%(ticket_id)s, %(author_id)s, %(body)s)
           RETURNING id""",
        {"ticket_id": ticket_id, "author_id": author_id, "body": body},
    ).fetchone()
    return conn.execute(COMMENT_SELECT + " WHERE cm.id = %(id)s", {"id": row["id"]}).fetchone()
