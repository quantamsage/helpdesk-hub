"""Pydantic models: what the API accepts and returns (mirrors docs/openapi.yaml).

Request models use extra="forbid", so unknown fields such as "role" are
rejected instead of silently ignored.
"""
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

Role = Literal["customer", "staff"]
TicketStatus = Literal["open", "in_progress", "resolved"]
TicketPriority = Literal["low", "normal", "high", "urgent"]


def _normalise_email(email: str) -> str:
    if len(email) > 254:
        raise ValueError("Email must be at most 254 characters.")
    return email.lower()


Email = Annotated[EmailStr, AfterValidator(_normalise_email)]


def trimmed(min_length: int, max_length: int):
    """Text with surrounding spaces removed, then length-checked."""
    return Annotated[str, StringConstraints(strip_whitespace=True, min_length=min_length, max_length=max_length)]


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---- Requests ---------------------------------------------------------------

class RegisterRequest(RequestModel):
    email: Email
    name: trimmed(1, 80)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(RequestModel):
    email: Email
    password: str = Field(min_length=1, max_length=128)


class TicketCreate(RequestModel):
    title: trimmed(5, 120)
    description: trimmed(10, 5000)


class TicketUpdate(RequestModel):
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    assignee_id: UUID | None = None  # explicit null means "unassign"

    @model_validator(mode="after")
    def check_fields(self):
        sent = self.model_fields_set  # fields actually present in the JSON
        if not sent:
            raise ValueError("Send at least one of: status, priority, assignee_id.")
        if "status" in sent and self.status is None:
            raise ValueError("status cannot be null.")
        if "priority" in sent and self.priority is None:
            raise ValueError("priority cannot be null.")
        return self


class CommentCreate(RequestModel):
    body: trimmed(1, 2000)
    # Staff-only. A customer sending true gets a 403.
    internal: bool = False


# ---- Responses --------------------------------------------------------------

class Health(BaseModel):
    status: Literal["ok"]


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"]
    expires_in: int


class User(BaseModel):
    id: UUID
    email: str
    name: str
    role: Role
    created_at: datetime


class UserSummary(BaseModel):
    id: UUID
    name: str


class StaffList(BaseModel):
    items: list[UserSummary]


class Ticket(BaseModel):
    id: UUID
    title: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    customer: UserSummary
    assignee: UserSummary | None
    created_at: datetime
    updated_at: datetime
    first_response_at: datetime | None
    due_at: datetime
    overdue: bool


class TicketList(BaseModel):
    items: list[Ticket]
    total: int
    limit: int
    offset: int


class CommentAuthor(BaseModel):
    id: UUID
    name: str
    role: Role


class Comment(BaseModel):
    id: UUID
    ticket_id: UUID
    author: CommentAuthor
    body: str
    internal: bool
    created_at: datetime


class CommentList(BaseModel):
    items: list[Comment]
