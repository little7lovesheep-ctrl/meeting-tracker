import aiosqlite
import httpx
from typing import List, Optional, Dict
from config import DB_PATH


async def get_all_channels() -> List[dict]:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM dingtalk_channels")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_channel_by_name(name: str) -> Optional[dict]:
    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM dingtalk_channels WHERE name = ?", (name,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def send_to_channel(channel_name: str, title: str, text: str, at_user_ids: Optional[List[str]] = None):
    channel = await get_channel_by_name(channel_name)
    if not channel:
        print(f"[钉钉] 群 '{channel_name}' 未配置，跳过推送")
        return

    msg = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": text
        },
        "at": {
            "atUserIds": at_user_ids or [],
            "isAtAll": False
        }
    }

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(channel["webhook_url"], json=msg)
        print(f"[钉钉] 推送到 '{channel_name}': {resp.status_code}")


async def send_to_all_channels(title: str, text: str, at_user_ids: Optional[List[str]] = None):
    channels = await get_all_channels()
    for ch in channels:
        await send_to_channel(ch["name"], title, text, at_user_ids)


async def send_checkpoint_reminder(action_title: str, assignee_name: str,
                                    checkpoint_desc: str, action_id: int,
                                    channel_name: Optional[str] = None,
                                    dingtalk_id: Optional[str] = None):
    text = (
        f"### 行动项Check提醒\n\n"
        f"**任务**: {action_title}\n\n"
        f"**责任人**: {assignee_name}\n\n"
        f"**检查点**: {checkpoint_desc}\n\n"
        f"请及时更新进度"
    )
    at_ids = [dingtalk_id] if dingtalk_id else []

    if channel_name:
        await send_to_channel(channel_name, "行动项Check提醒", text, at_ids)
    else:
        await send_to_all_channels("行动项Check提醒", text, at_ids)


async def send_overdue_summary(overdue_items: List[dict], channel_name: Optional[str] = None):
    if not overdue_items:
        return

    lines = ["### 逾期行动项汇总\n"]
    for item in overdue_items:
        lines.append(
            f"- **{item['title']}** | 责任人: {item['assignee_name'] or '未分配'} "
            f"| 截止: {item['due_date']}"
        )
    lines.append(f"\n共 **{len(overdue_items)}** 项逾期，请跟进")

    if channel_name:
        await send_to_channel(channel_name, "逾期行动项汇总", "\n".join(lines))
    else:
        await send_to_all_channels("逾期行动项汇总", "\n".join(lines))
