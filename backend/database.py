import aiosqlite
from config import DB_PATH

DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT,
    dingtalk_id TEXT,
    role TEXT DEFAULT 'member',
    password_hash TEXT,
    sort_order INTEGER DEFAULT 99,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS meetings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    meeting_date DATE,
    channel_name TEXT,
    status TEXT DEFAULT 'draft',
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS action_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id INTEGER REFERENCES meetings(id),
    title TEXT NOT NULL,
    description TEXT,
    assignee_id INTEGER REFERENCES users(id),
    assignee_name TEXT,
    watcher_name TEXT,
    status TEXT DEFAULT 'todo',
    priority TEXT DEFAULT 'medium',
    due_date DATE,
    channel_name TEXT,
    confirmed INTEGER DEFAULT 0,
    confirmed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_item_id INTEGER REFERENCES action_items(id),
    check_date TIMESTAMP NOT NULL,
    description TEXT,
    notified INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS feedbacks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_item_id INTEGER REFERENCES action_items(id),
    user_id INTEGER REFERENCES users(id),
    content TEXT NOT NULL,
    progress INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dingtalk_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    webhook_url TEXT NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


async def get_db():
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


async def init_db():
    async with aiosqlite.connect(str(DB_PATH)) as db:
        await db.executescript(SCHEMA)
        await migrate_db(db)
        await db.commit()


async def migrate_db(db: aiosqlite.Connection):
    """轻量迁移：兼容已部署的旧 SQLite 数据库。"""
    cursor = await db.execute("PRAGMA table_info(action_items)")
    columns = {row[1] for row in await cursor.fetchall()}
    if "watcher_name" not in columns:
        await db.execute("ALTER TABLE action_items ADD COLUMN watcher_name TEXT")
