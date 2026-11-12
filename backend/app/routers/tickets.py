"""Tickets and their comments.

Access rules:
- Customers see and comment on their OWN tickets only. Anyone else's ticket
  is reported as "not found", so its existence isn't revealed.
- Staff see every ticket and are the only ones who can change it.
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from psycopg import Connection

from .. import repo
from ..db import DbConn
from ..deps import CurrentUser, CustomerUser, StaffUser
from ..errors import ApiError, field_error, not_found
from ..schemas import Comment, CommentCreate, CommentList, Ticket, TicketCreate, TicketList, TicketStatus, TicketUpdate

router = APIRouter(prefix="/tickets", tags=["tickets"])


# ---- Helpers ----------------------------------------------------------------

def get_visible_ticket(conn: Connection, ticket_id: UUID, user: dict) -> dict:
    """The ownership check used by every single-ticket route."""
    ticket = repo.get_ticket(conn, ticket_id)
    if ticket is None:
        raise not_found()
    if user["role"] == "customer" and ticket["customer_id"] != user["id"]:
        raise not_found()  # not 403: don't reveal that the ticket exists
    return ticket


def ticket_out(row: dict) -> dict:
    assignee = None
    if row["assignee_id"] is not None:
        assignee = {"id": row["assignee_id"], "name": row["assignee_name"]}
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "status": row["status"],
        "customer": {"id": row["customer_id"], "name": row["customer_name"]},
        "assignee": assignee,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def comment_out(row: dict) -> dict:
    return {
        "id": row["id"],
        "ticket_id": row["ticket_id"],
        "author": {"id": row["author_id"], "name": row["author_name"], "role": row["author_role"]},
        "body": row["body"],
        "created_at": row["created_at"],
    }


def parse_assignee_filter(value: str | None, user: dict) -> UUID | str | None:
    """'me' -> your id, 'none' -> unassigned, otherwise a staff user id."""
    if value is None:
        return None
    if user["role"] != "staff":
        raise ApiError(403, "forbidden", "Only staff can filter by assignee.")
    if value == "me":
        return user["id"]
    if value == "none":
        return "none"
    try:
        return UUID(value)
    except ValueError:
        raise field_error("assignee", 'Use "me", "none" or a staff user id.')


# ---- Tickets ----------------------------------------------------------------

@router.get("", response_model=TicketList)
def list_tickets(
    user: CurrentUser,
    conn: DbConn,
    status: TicketStatus | None = None,
    assignee: Annotated[str | None, Query(max_length=36)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    rows, total = repo.list_tickets(
        conn,
        # The key ownership rule for lists: customers are always filtered to themselves.
        customer_id=user["id"] if user["role"] == "customer" else None,
        status=status,
        assignee=parse_assignee_filter(assignee, user),
        limit=limit,
        offset=offset,
    )
    return {"items": [ticket_out(r) for r in rows], "total": total, "limit": limit, "offset": offset}


@router.post("", status_code=201, response_model=Ticket)
def create_ticket(body: TicketCreate, user: CustomerUser, conn: DbConn):
    return ticket_out(repo.create_ticket(conn, user["id"], body.title, body.description))


@router.get("/{ticket_id}", response_model=Ticket)
def get_ticket(ticket_id: UUID, user: CurrentUser, conn: DbConn):
    return ticket_out(get_visible_ticket(conn, ticket_id, user))


@router.patch("/{ticket_id}", response_model=Ticket)
def update_ticket(ticket_id: UUID, body: TicketUpdate, user: StaffUser, conn: DbConn):
    get_visible_ticket(conn, ticket_id, user)  # 404 if it doesn't exist

    change_assignee = "assignee_id" in body.model_fields_set
    if change_assignee and body.assignee_id is not None and not repo.is_staff(conn, body.assignee_id):
        raise field_error("assignee_id", "Tickets can only be assigned to a staff member.")

    row = repo.update_ticket(
        conn, ticket_id, status=body.status, change_assignee=change_assignee, assignee_id=body.assignee_id
    )
    return ticket_out(row)


# ---- Comments ---------------------------------------------------------------

@router.get("/{ticket_id}/comments", response_model=CommentList)
def list_comments(ticket_id: UUID, user: CurrentUser, conn: DbConn):
    get_visible_ticket(conn, ticket_id, user)
    return {"items": [comment_out(r) for r in repo.list_comments(conn, ticket_id)]}


@router.post("/{ticket_id}/comments", status_code=201, response_model=Comment)
def add_comment(ticket_id: UUID, body: CommentCreate, user: CurrentUser, conn: DbConn):
    get_visible_ticket(conn, ticket_id, user)
    comment = repo.create_comment(conn, ticket_id, user["id"], body.body)
    repo.touch_ticket(conn, ticket_id)  # a reply counts as activity on the ticket
    return comment_out(comment)
