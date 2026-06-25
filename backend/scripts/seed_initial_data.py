import argparse
import asyncio
import json
from pathlib import Path

import aiosqlite
from passlib.context import CryptContext

from config import DB_PATH
from database import init_db


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


DEFAULT_PASSWORD = "123456"


async def upsert_user(db, user):
    name = user["name"].strip()
    role = user.get("role", "member")
    sort_order = user.get("sort_order", 99)
    password = user.get("password", DEFAULT_PASSWORD)
    password_hash = pwd_context.hash(password) if password else None

    row = await (await db.execute("SELECT id FROM users WHERE name = ?", (name,))).fetchone()
    if row:
        await db.execute(
            """UPDATE users
               SET role = ?, sort_order = ?, password_hash = COALESCE(?, password_hash)
               WHERE name = ?""",
            (role, sort_order, password_hash, name),
        )
    else:
        await db.execute(
            """INSERT INTO users (name, role, password_hash, sort_order)
               VALUES (?, ?, ?, ?)""",
            (name, role, password_hash, sort_order),
        )


async def upsert_channel(db, channel):
    name = channel["name"].strip()
    webhook_url = channel.get("webhook_url", "").strip()
    description = channel.get("description")

    if not webhook_url or webhook_url.startswith("REPLACE_WITH_"):
        print(f"[skip] {name}: webhook_url 未配置")
        return

    row = await (await db.execute("SELECT id FROM dingtalk_channels WHERE name = ?", (name,))).fetchone()
    if row:
        await db.execute(
            """UPDATE dingtalk_channels
               SET webhook_url = ?, description = ?
               WHERE name = ?""",
            (webhook_url, description, name),
        )
    else:
        await db.execute(
            """INSERT INTO dingtalk_channels (name, webhook_url, description)
               VALUES (?, ?, ?)""",
            (name, webhook_url, description),
        )


async def seed(path):
    await init_db()
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    async with aiosqlite.connect(str(DB_PATH)) as db:
        for user in data.get("users", []):
            await upsert_user(db, user)

        for channel in data.get("channels", []):
            await upsert_channel(db, channel)

        await db.commit()

    print(f"初始化完成：{len(data.get('users', []))} 个成员，{len(data.get('channels', []))} 个钉钉群")


def main():
    parser = argparse.ArgumentParser(description="初始化团队成员和钉钉群配置")
    parser.add_argument(
        "--file",
        default="seed_data.json",
        help="初始化数据 JSON 文件路径，默认读取 backend/seed_data.json",
    )
    args = parser.parse_args()
    asyncio.run(seed(args.file))


if __name__ == "__main__":
    main()
