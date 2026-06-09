from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import aiosqlite
from database import get_db

router = APIRouter(prefix="/api/channels", tags=["channels"])


class ChannelCreate(BaseModel):
    name: str
    webhook_url: str
    description: Optional[str] = None


@router.get("")
async def list_channels(db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute("SELECT id, name, description, created_at FROM dingtalk_channels")
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


@router.post("")
async def create_channel(req: ChannelCreate, db: aiosqlite.Connection = Depends(get_db)):
    try:
        cursor = await db.execute(
            "INSERT INTO dingtalk_channels (name, webhook_url, description) VALUES (?, ?, ?)",
            (req.name, req.webhook_url, req.description)
        )
        await db.commit()
        return {"id": cursor.lastrowid, "name": req.name}
    except Exception as e:
        if "UNIQUE" in str(e):
            raise HTTPException(status_code=400, detail=f"群名 '{req.name}' 已存在")
        raise


@router.put("/{channel_id}")
async def update_channel(channel_id: int, req: ChannelCreate,
                         db: aiosqlite.Connection = Depends(get_db)):
    await db.execute(
        "UPDATE dingtalk_channels SET name=?, webhook_url=?, description=? WHERE id=?",
        (req.name, req.webhook_url, req.description, channel_id)
    )
    await db.commit()
    return {"ok": True}


@router.delete("/{channel_id}")
async def delete_channel(channel_id: int, db: aiosqlite.Connection = Depends(get_db)):
    await db.execute("DELETE FROM dingtalk_channels WHERE id = ?", (channel_id,))
    await db.commit()
    return {"ok": True}
