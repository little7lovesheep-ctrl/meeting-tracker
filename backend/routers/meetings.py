from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List
import aiosqlite
from database import get_db
from services.ai_parser import parse_meeting_notes
from services.dingtalk import send_to_channel

import os

router = APIRouter(prefix="/api/meetings", tags=["meetings"])

FRONTEND_HOST = os.getenv("FRONTEND_HOST", "http://localhost:5173")


def get_frontend_url():
    return FRONTEND_HOST


class ParseRequest(BaseModel):
    raw_text: str
    meeting_date: Optional[date] = None


class CheckpointData(BaseModel):
    check_date: str
    description: Optional[str] = None


class ActionItemData(BaseModel):
    title: str
    description: Optional[str] = None
    assignee_name: Optional[str] = None
    priority: str = "medium"
    due_date: Optional[str] = None
    checkpoints: List[CheckpointData] = []


class DraftRequest(BaseModel):
    raw_text: str
    meeting_date: Optional[date] = None
    title: str
    channel_name: str
    action_items: List[ActionItemData]


class ItemUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee_name: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None
    checkpoints: Optional[List[CheckpointData]] = None


@router.get("")
async def list_meetings(db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute(
        "SELECT id, title, meeting_date, channel_name, status, created_at FROM meetings ORDER BY created_at DESC"
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


@router.post("/parse")
async def parse_meeting(req: ParseRequest):
    """仅AI解析，不入库。"""
    meeting_date = req.meeting_date or date.today()
    meeting_date_str = meeting_date.isoformat()

    try:
        parsed = await parse_meeting_notes(req.raw_text, meeting_date_str)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI解析失败: {str(e)}")

    return parsed


@router.post("/upload-file")
async def upload_file(file: UploadFile = File(...)):
    """上传文件，提取文本内容返回。支持 txt/md/docx/pdf"""
    ext = file.filename.split(".")[-1].lower() if file.filename else ""
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过10MB")

    if ext in ("txt", "md"):
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("gbk", errors="ignore")
        return {"text": text}

    elif ext == "docx":
        try:
            import docx
            import io
            doc = docx.Document(io.BytesIO(content))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            return {"text": text}
        except ImportError:
            raise HTTPException(status_code=400, detail="服务器未安装docx解析库，请先安装python-docx")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"docx解析失败: {str(e)}")

    elif ext == "pdf":
        try:
            import fitz  # PyMuPDF
            import io
            doc = fitz.open(stream=content, filetype="pdf")
            text = "\n".join(page.get_text() for page in doc)
            return {"text": text}
        except ImportError:
            raise HTTPException(status_code=400, detail="服务器未安装PDF解析库，请先安装pymupdf")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PDF解析失败: {str(e)}")

    else:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: .{ext}")


@router.post("/draft")
async def create_draft(req: DraftRequest, db: aiosqlite.Connection = Depends(get_db)):
    """存为草稿 + 推送钉钉让团队确认。"""
    meeting_date_str = (req.meeting_date or date.today()).isoformat()

    cursor = await db.execute(
        "INSERT INTO meetings (title, raw_text, meeting_date, channel_name, status) VALUES (?, ?, ?, ?, 'draft')",
        (req.title, req.raw_text, meeting_date_str, req.channel_name)
    )
    meeting_id = cursor.lastrowid

    action_items_result = []
    for item in req.action_items:
        assignee_id = None
        assignee_name = item.assignee_name or ""

        if assignee_name:
            ac = await db.execute(
                "SELECT id FROM users WHERE name = ?", (assignee_name,)
            )
            user_row = await ac.fetchone()
            if user_row:
                assignee_id = user_row["id"]

        ai_cursor = await db.execute(
            """INSERT INTO action_items
               (meeting_id, title, description, assignee_id, assignee_name, status, priority, due_date, channel_name)
               VALUES (?, ?, ?, ?, ?, 'todo', ?, ?, ?)""",
            (meeting_id, item.title, item.description,
             assignee_id, assignee_name, item.priority,
             item.due_date, req.channel_name)
        )
        action_item_id = ai_cursor.lastrowid

        for cp in item.checkpoints:
            await db.execute(
                "INSERT INTO checkpoints (action_item_id, check_date, description) VALUES (?, ?, ?)",
                (action_item_id, cp.check_date, cp.description)
            )

        action_items_result.append({
            "id": action_item_id,
            "title": item.title,
            "assignee_name": assignee_name,
            "assignee_id": assignee_id,
            "priority": item.priority,
            "due_date": item.due_date,
            "checkpoints": [{"check_date": cp.check_date, "description": cp.description} for cp in item.checkpoints]
        })

    await db.commit()

    # 推送钉钉
    await _send_draft_to_dingtalk(req.title, meeting_date_str, action_items_result, meeting_id, req.channel_name)

    return {
        "meeting_id": meeting_id,
        "title": req.title,
        "status": "draft",
        "action_items": action_items_result
    }


async def _send_draft_to_dingtalk(title: str, meeting_date: str, items: list, meeting_id: int, channel_name: str):
    """构造钉钉消息并推送"""
    # 按责任人分组
    by_assignee = {}
    for item in items:
        name = item["assignee_name"] or "未分配"
        by_assignee.setdefault(name, []).append(item)

    priority_label = {"high": "高优", "medium": "中优", "low": "低优"}

    lines = [f"### 会议行动项确认\n"]
    lines.append(f"**会议**: {title}（{meeting_date}）\n")
    lines.append("---\n")

    for assignee, assignee_items in by_assignee.items():
        lines.append(f"**{assignee}（{len(assignee_items)}项）**\n")
        for i, item in enumerate(assignee_items, 1):
            p = priority_label.get(item["priority"], "中优")
            due = item["due_date"] or "待定"
            lines.append(f"{i}. {item['title']} | 截止: {due} | {p}\n")
        lines.append("")

    lines.append("---\n")
    edit_url = f"{get_frontend_url()}/meeting-edit/{meeting_id}"
    lines.append(f"请各位确认自己的行动项和截止时间，如需调整请点击：\n\n[查看并修改]({edit_url})")

    text = "\n".join(lines)
    await send_to_channel(channel_name, "会议行动项确认", text)


@router.put("/{meeting_id}/activate")
async def activate_meeting(meeting_id: int, db: aiosqlite.Connection = Depends(get_db)):
    """文静确认，将会议从draft变为active。"""
    cursor = await db.execute("SELECT status FROM meetings WHERE id = ?", (meeting_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="会议不存在")
    if row["status"] == "active":
        raise HTTPException(status_code=400, detail="该会议已生效")

    await db.execute("UPDATE meetings SET status = 'active' WHERE id = ?", (meeting_id,))
    await db.commit()
    return {"ok": True, "status": "active"}


@router.get("/{meeting_id}/edit")
async def get_meeting_for_edit(meeting_id: int, db: aiosqlite.Connection = Depends(get_db)):
    """公开接口，团队成员通过链接查看并编辑。"""
    cursor = await db.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,))
    meeting = await cursor.fetchone()
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")

    ai_cursor = await db.execute(
        "SELECT * FROM action_items WHERE meeting_id = ? ORDER BY id", (meeting_id,)
    )
    items = await ai_cursor.fetchall()

    result_items = []
    for item in items:
        cp_cursor = await db.execute(
            "SELECT * FROM checkpoints WHERE action_item_id = ? ORDER BY check_date", (item["id"],)
        )
        cps = await cp_cursor.fetchall()
        item_dict = dict(item)
        item_dict["checkpoints"] = [dict(cp) for cp in cps]
        result_items.append(item_dict)

    return {
        **dict(meeting),
        "action_items": result_items
    }


@router.put("/{meeting_id}/items/{item_id}")
async def update_action_item(meeting_id: int, item_id: int, req: ItemUpdateRequest,
                             db: aiosqlite.Connection = Depends(get_db)):
    """团队成员修改某个行动项。"""
    # 确认item属于该会议
    cursor = await db.execute(
        "SELECT id FROM action_items WHERE id = ? AND meeting_id = ?", (item_id, meeting_id)
    )
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="行动项不存在")

    # 更新基础字段
    updates = []
    params = []
    for field in ["title", "description", "assignee_name", "priority", "due_date"]:
        value = getattr(req, field)
        if value is not None:
            updates.append(f"{field} = ?")
            params.append(value)

    if updates:
        params.append(item_id)
        await db.execute(f"UPDATE action_items SET {', '.join(updates)} WHERE id = ?", params)

    # 如果传了checkpoints，重建
    if req.checkpoints is not None:
        await db.execute("DELETE FROM checkpoints WHERE action_item_id = ?", (item_id,))
        for cp in req.checkpoints:
            await db.execute(
                "INSERT INTO checkpoints (action_item_id, check_date, description) VALUES (?, ?, ?)",
                (item_id, cp.check_date, cp.description)
            )

    # 修改保存即视为确认
    await db.execute(
        "UPDATE action_items SET confirmed = 1, confirmed_at = ? WHERE id = ?",
        (datetime.now().isoformat(), item_id)
    )

    await db.commit()
    return {"ok": True}


@router.put("/{meeting_id}/items/{item_id}/confirm")
async def confirm_action_item(meeting_id: int, item_id: int,
                              db: aiosqlite.Connection = Depends(get_db)):
    """团队成员确认某个行动项（无异议）。"""
    cursor = await db.execute(
        "SELECT id FROM action_items WHERE id = ? AND meeting_id = ?", (item_id, meeting_id)
    )
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="行动项不存在")

    await db.execute(
        "UPDATE action_items SET confirmed = 1, confirmed_at = ? WHERE id = ?",
        (datetime.now().isoformat(), item_id)
    )
    await db.commit()
    return {"ok": True}


@router.get("/{meeting_id}")
async def get_meeting(meeting_id: int, db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,))
    meeting = await cursor.fetchone()
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")

    ai_cursor = await db.execute(
        "SELECT * FROM action_items WHERE meeting_id = ?", (meeting_id,)
    )
    items = await ai_cursor.fetchall()

    return {
        **dict(meeting),
        "action_items": [dict(item) for item in items]
    }
