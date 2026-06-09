from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import logging
import aiosqlite
from config import DB_PATH
from services.dingtalk import send_checkpoint_reminder, send_overdue_summary, send_to_channel

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def send_today_checkpoints():
    """每天9:00 推送今日到期的check节点"""
    try:
        await _send_today_checkpoints()
    except Exception as e:
        logger.error(f"[scheduler] send_today_checkpoints failed: {e}")


async def _send_today_checkpoints():
    today = datetime.now().date().isoformat()
    tomorrow = (datetime.now().date() + timedelta(days=1)).isoformat()

    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT cp.id as cp_id, cp.description as cp_desc, cp.check_date,
                      ai.id as action_id, ai.title as action_title,
                      ai.assignee_name, ai.channel_name
               FROM checkpoints cp
               JOIN action_items ai ON cp.action_item_id = ai.id
               JOIN meetings m ON ai.meeting_id = m.id
               WHERE cp.check_date >= ? AND cp.check_date < ?
               AND cp.notified = 0
               AND ai.status != 'done'
               AND m.status = 'active'""",
            (today, tomorrow)
        )
        rows = await cursor.fetchall()

        if not rows:
            return

        # 按群分组推送
        by_channel = {}
        for row in rows:
            ch = row["channel_name"] or "default"
            by_channel.setdefault(ch, []).append(row)

        for channel_name, items in by_channel.items():
            lines = ["### 今日待办Check节点\n"]
            for item in items:
                lines.append(
                    f"- **{item['action_title']}** | {item['assignee_name'] or '未分配'} "
                    f"| {item['cp_desc'] or '请更新进度'}"
                )
            lines.append(f"\n共 **{len(items)}** 项今日需确认进度")
            await send_to_channel(channel_name, "今日待办Check", "\n".join(lines))

        # 标记为已通知
        for row in rows:
            await db.execute("UPDATE checkpoints SET notified = 1 WHERE id = ?", (row["cp_id"],))
        await db.commit()


async def send_daily_overdue_summary():
    """每天9:30 推送逾期未完成项"""
    try:
        await _send_daily_overdue_summary()
    except Exception as e:
        logger.error(f"[scheduler] send_daily_overdue_summary failed: {e}")


async def _send_daily_overdue_summary():
    today = datetime.now().date().isoformat()

    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT ai.id, ai.title, ai.assignee_name, ai.due_date, ai.channel_name
               FROM action_items ai
               JOIN meetings m ON ai.meeting_id = m.id
               WHERE ai.due_date < ? AND ai.status NOT IN ('done')
               AND m.status = 'active'""",
            (today,)
        )
        rows = await cursor.fetchall()
        items = [dict(row) for row in rows]

    if items:
        # 按群分组推送
        by_channel = {}
        for item in items:
            ch = item["channel_name"] or "default"
            by_channel.setdefault(ch, []).append(item)

        for channel_name, channel_items in by_channel.items():
            await send_overdue_summary(channel_items, channel_name)


async def send_tomorrow_due_reminder():
    """每天17:00 推送明天到期的行动项提前提醒"""
    try:
        await _send_tomorrow_due_reminder()
    except Exception as e:
        logger.error(f"[scheduler] send_tomorrow_due_reminder failed: {e}")


async def _send_tomorrow_due_reminder():
    tomorrow = (datetime.now().date() + timedelta(days=1)).isoformat()
    day_after = (datetime.now().date() + timedelta(days=2)).isoformat()

    async with aiosqlite.connect(str(DB_PATH)) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT ai.id, ai.title, ai.assignee_name, ai.due_date, ai.channel_name
               FROM action_items ai
               JOIN meetings m ON ai.meeting_id = m.id
               WHERE ai.due_date >= ? AND ai.due_date < ?
               AND ai.status NOT IN ('done')
               AND m.status = 'active'""",
            (tomorrow, day_after)
        )
        rows = await cursor.fetchall()

    if not rows:
        return

    by_channel = {}
    for row in rows:
        ch = row["channel_name"] or "default"
        by_channel.setdefault(ch, []).append(dict(row))

    for channel_name, items in by_channel.items():
        lines = ["### 明日到期提醒\n"]
        for item in items:
            lines.append(
                f"- **{item['title']}** | 责任人: {item['assignee_name'] or '未分配'} "
                f"| 截止: {item['due_date']}"
            )
        lines.append(f"\n共 **{len(items)}** 项明天到期，请提前完成")
        await send_to_channel(channel_name, "明日到期提醒", "\n".join(lines))


def setup_scheduler():
    # 工作日 9:00 — 今日check节点提醒
    scheduler.add_job(send_today_checkpoints,
                      CronTrigger(hour=9, minute=0, day_of_week='mon-fri'),
                      id="today_checkpoints")

    # 工作日 9:30 — 逾期汇总
    scheduler.add_job(send_daily_overdue_summary,
                      CronTrigger(hour=9, minute=30, day_of_week='mon-fri'),
                      id="daily_overdue")

    # 工作日 17:00 — 明日到期提前提醒
    scheduler.add_job(send_tomorrow_due_reminder,
                      CronTrigger(hour=17, minute=0, day_of_week='mon-fri'),
                      id="tomorrow_reminder")

    scheduler.start()
