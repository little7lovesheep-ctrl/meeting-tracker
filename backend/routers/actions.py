from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
import aiosqlite
from database import get_db
from models import ActionItemUpdate, FeedbackCreate

router = APIRouter(prefix="/api/actions", tags=["actions"])


@router.get("")
async def list_actions(
    status: str = Query(None),
    assignee_id: int = Query(None),
    overdue: bool = Query(False),
    db: aiosqlite.Connection = Depends(get_db)
):
    query = "SELECT * FROM action_items WHERE 1=1"
    params = []

    if status:
        query += " AND status = ?"
        params.append(status)
    if assignee_id:
        query += " AND assignee_id = ?"
        params.append(assignee_id)
    if overdue:
        today = datetime.now().date().isoformat()
        query += " AND due_date < ? AND status != 'done'"
        params.append(today)

    query += " ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, due_date"
    cursor = await db.execute(query, params)
    items = await cursor.fetchall()

    result = []
    for item in items:
        item_dict = dict(item)
        cp_cursor = await db.execute(
            "SELECT * FROM checkpoints WHERE action_item_id = ?", (item["id"],)
        )
        item_dict["checkpoints"] = [dict(cp) for cp in await cp_cursor.fetchall()]
        result.append(item_dict)

    return result


@router.get("/overdue")
async def list_overdue(db: aiosqlite.Connection = Depends(get_db)):
    today = datetime.now().date().isoformat()
    cursor = await db.execute(
        """SELECT * FROM action_items
           WHERE due_date < ? AND status NOT IN ('done')
           ORDER BY due_date""",
        (today,)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


@router.get("/dashboard")
async def dashboard(db: aiosqlite.Connection = Depends(get_db)):
    today = datetime.now().date().isoformat()

    total = await (await db.execute("SELECT COUNT(*) as c FROM action_items")).fetchone()
    done = await (await db.execute("SELECT COUNT(*) as c FROM action_items WHERE status='done'")).fetchone()
    overdue = await (await db.execute(
        "SELECT COUNT(*) as c FROM action_items WHERE due_date < ? AND status != 'done'", (today,)
    )).fetchone()
    in_progress = await (await db.execute(
        "SELECT COUNT(*) as c FROM action_items WHERE status='in_progress'"
    )).fetchone()

    assignee_cursor = await db.execute(
        """SELECT assignee_name, COUNT(*) as count,
                  SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as done_count
           FROM action_items
           WHERE assignee_name IS NOT NULL
           GROUP BY assignee_name"""
    )
    by_assignee = [dict(row) for row in await assignee_cursor.fetchall()]

    return {
        "total": total["c"],
        "done": done["c"],
        "in_progress": in_progress["c"],
        "overdue": overdue["c"],
        "by_assignee": by_assignee
    }


@router.put("/{action_id}")
async def update_action(action_id: int, req: ActionItemUpdate,
                        db: aiosqlite.Connection = Depends(get_db)):
    updates = []
    params = []
    for field, value in req.model_dump(exclude_none=True).items():
        if field == "due_date":
            value = value.isoformat()
        updates.append(f"{field} = ?")
        params.append(value)

    if not updates:
        raise HTTPException(status_code=400, detail="无更新字段")

    if req.status == "done":
        updates.append("completed_at = ?")
        params.append(datetime.now().isoformat())

    params.append(action_id)
    await db.execute(
        f"UPDATE action_items SET {', '.join(updates)} WHERE id = ?", params
    )
    await db.commit()
    return {"ok": True}


@router.delete("/{action_id}")
async def delete_action(action_id: int, db: aiosqlite.Connection = Depends(get_db)):
    await db.execute("DELETE FROM checkpoints WHERE action_item_id = ?", (action_id,))
    await db.execute("DELETE FROM feedbacks WHERE action_item_id = ?", (action_id,))
    await db.execute("DELETE FROM action_items WHERE id = ?", (action_id,))
    await db.commit()
    return {"ok": True}


@router.post("/{action_id}/feedback")
async def add_feedback(action_id: int, req: FeedbackCreate,
                       db: aiosqlite.Connection = Depends(get_db)):
    await db.execute(
        "INSERT INTO feedbacks (action_item_id, content, progress) VALUES (?, ?, ?)",
        (action_id, req.content, req.progress)
    )
    if req.progress >= 100:
        await db.execute(
            "UPDATE action_items SET status = 'done', completed_at = ? WHERE id = ?",
            (datetime.now().isoformat(), action_id)
        )
    elif req.progress > 0:
        await db.execute(
            "UPDATE action_items SET status = 'in_progress' WHERE id = ? AND status = 'todo'",
            (action_id,)
        )
    await db.commit()
    return {"ok": True}


@router.get("/{action_id}/feedbacks")
async def list_feedbacks(action_id: int, db: aiosqlite.Connection = Depends(get_db)):
    cursor = await db.execute(
        """SELECT f.*, u.name as user_name
           FROM feedbacks f
           LEFT JOIN users u ON f.user_id = u.id
           WHERE f.action_item_id = ?
           ORDER BY f.created_at DESC""",
        (action_id,)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]
