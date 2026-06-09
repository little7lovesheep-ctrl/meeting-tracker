from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
from fastapi import APIRouter, Depends, HTTPException
import aiosqlite
from database import get_db
from models import UserCreate, UserOut, LoginRequest
from config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_HOURS

router = APIRouter(prefix="/api/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_token(user_id: int, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    return jwt.encode({"sub": str(user_id), "role": role, "exp": expire},
                      JWT_SECRET, algorithm=JWT_ALGORITHM)


@router.post("/login")
async def login(req: LoginRequest, db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM users WHERE name = ?", (req.name,))
    user = await cursor.fetchone()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    if not user["password_hash"]:
        raise HTTPException(status_code=401, detail="该用户未设置密码，请联系管理员")

    if not pwd_context.verify(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="密码错误")

    token = create_token(user["id"], user["role"])
    return {"token": token, "user": {"id": user["id"], "name": user["name"], "role": user["role"]}}


@router.post("/register")
async def register(req: UserCreate, db: aiosqlite.Connection = Depends(get_db)):
    password_hash = pwd_context.hash(req.password) if req.password else None
    cursor = await db.execute(
        "INSERT INTO users (name, phone, dingtalk_id, role, password_hash) VALUES (?, ?, ?, ?, ?)",
        (req.name, req.phone, req.dingtalk_id, "member", password_hash)
    )
    await db.commit()
    return {"id": cursor.lastrowid, "name": req.name}
