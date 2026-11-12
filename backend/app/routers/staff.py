from fastapi import APIRouter

from .. import repo
from ..db import DbConn
from ..deps import StaffUser
from ..schemas import StaffList

router = APIRouter(tags=["staff"])


@router.get("/staff", response_model=StaffList)
def list_staff(user: StaffUser, conn: DbConn):
    return {"items": repo.list_staff(conn)}
