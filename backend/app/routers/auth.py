from fastapi import APIRouter
from psycopg.errors import UniqueViolation

from .. import repo
from ..db import DbConn
from ..deps import AppSettings, CurrentUser
from ..errors import ApiError
from ..schemas import LoginRequest, RegisterRequest, TokenResponse, User
from ..security import create_access_token, hash_password, verify_password, waste_time_like_a_real_check

router = APIRouter(prefix="/auth", tags=["auth"])

# Same message for "no such email" and "wrong password", so attackers
# can't use login to find out who has an account.
_BAD_LOGIN = ApiError(401, "unauthorized", "Incorrect email or password.")


@router.post("/register", status_code=201, response_model=User)
def register(body: RegisterRequest, conn: DbConn):
    try:
        return repo.create_customer(conn, body.email, body.name, hash_password(body.password))
    except UniqueViolation:
        raise ApiError(409, "conflict", "An account with this email already exists.")


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, conn: DbConn, settings: AppSettings):
    user = repo.get_login_details(conn, body.email)
    if user is None:
        waste_time_like_a_real_check(body.password)
        raise _BAD_LOGIN
    if not verify_password(body.password, user["password_hash"]):
        raise _BAD_LOGIN

    token = create_access_token(user["id"], settings.jwt_secret, settings.access_token_minutes)
    return {"access_token": token, "token_type": "bearer", "expires_in": settings.access_token_minutes * 60}


@router.get("/me", response_model=User)
def me(user: CurrentUser):
    return user
