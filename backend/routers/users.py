from fastapi import APIRouter, Depends
import aiosqlite
from database import get_db
from models import UserCreate, UserOut

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("")
async def list_users(db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute("SELECT id, name, phone, dingtalk_id, role FROM users ORDER BY sort_order, id")
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


@router.post("")
async def create_user(user: UserCreate, db: aiosqlite.Connection = Depends(get_db)):
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    password_hash = pwd_context.hash(user.password) if user.password else None

    cursor = await db.execute(
        "INSERT INTO users (name, phone, dingtalk_id, role, password_hash) VALUES (?, ?, ?, ?, ?)",
        (user.name, user.phone, user.dingtalk_id, user.role, password_hash)
    )
    await db.commit()
    return {"id": cursor.lastrowid, "name": user.name, "role": user.role}
