"""Who is making this request, and are they allowed to?"""
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import repo
from .config import Settings
from .db import DbConn
from .errors import ApiError
from .security import read_access_token

_bearer = HTTPBearer(auto_error=False)  # we return our own 401 format instead


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


AppSettings = Annotated[Settings, Depends(get_settings)]


def get_current_user(
    conn: DbConn,
    settings: AppSettings,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict:
    if credentials is None:
        raise ApiError(401, "unauthorized", "Please log in.")

    user_id = read_access_token(credentials.credentials, settings.jwt_secret)
    # Load the user fresh on every request, so a deleted account or a role
    # change takes effect immediately rather than when the token expires.
    user = repo.get_user_by_id(conn, user_id) if user_id else None
    if user is None:
        raise ApiError(401, "unauthorized", "Your session is invalid or has expired. Please log in again.")
    return user


CurrentUser = Annotated[dict, Depends(get_current_user)]


def require_staff(user: CurrentUser) -> dict:
    if user["role"] != "staff":
        raise ApiError(403, "forbidden", "Only staff can do this.")
    return user


def require_customer(user: CurrentUser) -> dict:
    if user["role"] != "customer":
        raise ApiError(403, "forbidden", "Only customers can do this.")
    return user


StaffUser = Annotated[dict, Depends(require_staff)]
CustomerUser = Annotated[dict, Depends(require_customer)]
