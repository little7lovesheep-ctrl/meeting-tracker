from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
import aiosqlite
from database import get_db
from models import ActionItemUpdate, FeedbackCreate

router = APIRouter(prefix="/api/actions", tags=["actions"])


@router.get("")
async def list_actions(
    status: str = Query(None),
    assignee_id: int = Query(None),
    watcher_name: str = Query(None),
    focus_owner: str = Query(None),
    overdue: bool = Query(False),
    db: aiosqlite.Connection = Depends(get_db)
):
    query = """
        SELECT ai.*
        FROM action_items ai
        LEFT JOIN meetings m ON ai.meeting_id = m.id
        WHERE (ai.meeting_id IS NULL OR m.status = 'active')
    """
    params = []

    if status:
        query += " AND ai.status = ?"
        params.append(status)
    if assignee_id:
        query += " AND ai.assignee_id = ?"
        params.append(assignee_id)
    if watcher_name:
        query += " AND ai.watcher_name = ?"
        params.append(watcher_name)
    if overdue:
        today = datetime.now().date().isoformat()
        query += " AND ai.due_date < ? AND ai.status != 'done'"
        params.append(today)
    if focus_owner:
        today = datetime.now().date()
        upcoming = (today + timedelta(days=1)).isoformat()
        query += """
            AND ai.status != 'done'
            AND (
                ai.watcher_name = ?
                OR ai.priority = 'high'
                OR (ai.due_date IS NOT NULL AND ai.due_date < ?)
                OR EXISTS (
                    SELECT 1 FROM checkpoints cp
                    WHERE cp.action_item_id = ai.id
                      AND date(cp.check_date) <= date(?)
                      AND cp.notified = 0
                )
            )
        """
        params.extend([focus_owner, today.isoformat(), upcoming])

    query += " ORDER BY CASE ai.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END, ai.due_date"
    cursor = await db.execute(query, params)
    items = await cursor.fetchall()

    result = []
    for item in items:
        item_dict = dict(item)
        cp_cursor = await db.execute(
            "SELECT * FROM checkpoints WHERE action_item_id = ?", (item["id"],)
        )
        item_dict["checkpoints"] = [dict(cp) for cp in await cp_cursor.fetchall()]
        item_dict["focus_reasons"] = get_focus_reasons(item_dict)
        result.append(item_dict)

    return result


def get_focus_reasons(item: dict) -> list[str]:
    today = datetime.now().date()
    reasons = []
    if item.get("watcher_name"):
        reasons.append(f"{item['watcher_name']}关注")
    if item.get("priority") == "high":
        reasons.append("高优先级")
    due_date = item.get("due_date")
    if due_date:
        try:
            if datetime.fromisoformat(due_date).date() < today and item.get("status") != "done":
                reasons.append("已逾期")
        except ValueError:
            pass
    upcoming = today + timedelta(days=1)
    for checkpoint in item.get("checkpoints", []):
        check_date = checkpoint.get("check_date")
        if not check_date or checkpoint.get("notified"):
            continue
        try:
            if datetime.fromisoformat(check_date).date() <= upcoming:
                reasons.append("检查节点将至")
                break
        except ValueError:
            continue
    return reasons


@router.get("/overdue")
async def list_overdue(db: aiosqlite.Connection = Depends(get_db)):
    today = datetime.now().date().isoformat()
    cursor = await db.execute(
        """SELECT ai.*
           FROM action_items ai
           LEFT JOIN meetings m ON ai.meeting_id = m.id
           WHERE ai.due_date < ?
             AND ai.status NOT IN ('done')
             AND (ai.meeting_id IS NULL OR m.status = 'active')
           ORDER BY ai.due_date""",
        (today,)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


@router.get("/dashboard")
async def dashboard(db: aiosqlite.Connection = Depends(get_db)):
    today = datetime.now().date().isoformat()

    active_filter = "FROM action_items ai LEFT JOIN meetings m ON ai.meeting_id = m.id WHERE (ai.meeting_id IS NULL OR m.status = 'active')"
    total = await (await db.execute(f"SELECT COUNT(*) as c {active_filter}")).fetchone()
    done = await (await db.execute(f"SELECT COUNT(*) as c {active_filter} AND ai.status='done'")).fetchone()
    overdue = await (await db.execute(
        f"SELECT COUNT(*) as c {active_filter} AND ai.due_date < ? AND ai.status != 'done'", (today,)
    )).fetchone()
    in_progress = await (await db.execute(
        f"SELECT COUNT(*) as c {active_filter} AND ai.status='in_progress'"
    )).fetchone()

    assignee_cursor = await db.execute(
        """SELECT ai.assignee_name, COUNT(*) as count,
                  SUM(CASE WHEN ai.status='done' THEN 1 ELSE 0 END) as done_count
           FROM action_items ai
           LEFT JOIN meetings m ON ai.meeting_id = m.id
           WHERE ai.assignee_name IS NOT NULL
             AND (ai.meeting_id IS NULL OR m.status = 'active')
           GROUP BY ai.assignee_name"""
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
