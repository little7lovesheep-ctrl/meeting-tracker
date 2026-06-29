import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
import os
from pathlib import Path
import tempfile

import config
import database

TEST_DB_PATH = Path(tempfile.gettempdir()) / "meeting_tracker_test.db"
config.DB_PATH = TEST_DB_PATH
database.DB_PATH = TEST_DB_PATH

from main import app
from database import init_db


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """每个测试用新数据库"""
    if database.DB_PATH.exists():
        database.DB_PATH.unlink()
    await init_db()
    yield
    if database.DB_PATH.exists():
        database.DB_PATH.unlink()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def seeded_client(client):
    """预置团队成员和钉钉群"""
    await client.post("/api/users", json={"name": "文静", "role": "admin", "password": "123456"})
    await client.post("/api/users", json={"name": "吕彦", "role": "member", "password": "123456"})
    await client.post("/api/users", json={"name": "青哥", "role": "member", "password": "123456"})
    await client.post("/api/channels", json={"name": "测试群", "webhook_url": "https://example.com/webhook"})
    return client


# === 用户相关 ===

@pytest.mark.asyncio
async def test_create_user(client):
    resp = await client.post("/api/users", json={"name": "张三", "role": "member", "password": "123"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "张三"


@pytest.mark.asyncio
async def test_list_users(client):
    await client.post("/api/users", json={"name": "李四", "role": "member"})
    resp = await client.get("/api/users")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post("/api/users", json={"name": "文静", "role": "admin", "password": "123456"})
    resp = await client.post("/api/auth/login", json={"name": "文静", "password": "123456"})
    assert resp.status_code == 200
    assert "token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/users", json={"name": "文静", "role": "admin", "password": "123456"})
    resp = await client.post("/api/auth/login", json={"name": "文静", "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    resp = await client.post("/api/auth/login", json={"name": "不存在", "password": "123"})
    assert resp.status_code == 401


# === 钉钉群管理 ===

@pytest.mark.asyncio
async def test_create_channel(client):
    resp = await client.post("/api/channels", json={"name": "测试群", "webhook_url": "https://example.com/hook"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "测试群"


@pytest.mark.asyncio
async def test_duplicate_channel(client):
    await client.post("/api/channels", json={"name": "测试群", "webhook_url": "https://a.com"})
    resp = await client.post("/api/channels", json={"name": "测试群", "webhook_url": "https://b.com"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_channels(client):
    await client.post("/api/channels", json={"name": "群1", "webhook_url": "https://a.com"})
    await client.post("/api/channels", json={"name": "群2", "webhook_url": "https://b.com"})
    resp = await client.get("/api/channels")
    assert len(resp.json()) == 2


# === 会议草稿 ===

@pytest.mark.asyncio
async def test_create_draft(seeded_client):
    resp = await seeded_client.post("/api/meetings/draft", json={
        "raw_text": "测试内容",
        "meeting_date": "2026-06-09",
        "title": "测试会议",
        "channel_name": "测试群",
        "action_items": [
            {"title": "任务1", "assignee_name": "吕彦", "watcher_name": "文静", "priority": "high", "due_date": "2026-06-15", "checkpoints": [
                {"check_date": "2026-06-12", "description": "中期检查"}
            ]},
            {"title": "任务2", "assignee_name": "青哥", "priority": "medium", "due_date": "2026-06-20", "checkpoints": []}
        ]
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "draft"
    assert len(data["action_items"]) == 2
    assert data["action_items"][0]["assignee_id"] == 2  # 吕彦的ID
    assert data["action_items"][0]["watcher_name"] == "文静"


@pytest.mark.asyncio
async def test_draft_meeting_not_in_active_list(seeded_client):
    """draft状态的会议行动项不应出现在看板（仅active的才算）"""
    await seeded_client.post("/api/meetings/draft", json={
        "raw_text": "x", "meeting_date": "2026-06-09", "title": "草稿会议",
        "channel_name": "测试群", "action_items": [
            {"title": "草稿任务", "assignee_name": "吕彦", "priority": "medium", "due_date": "2026-06-15", "checkpoints": []}
        ]
    })
    resp = await seeded_client.get("/api/actions")
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_active_meeting_in_action_list(seeded_client):
    draft_resp = await seeded_client.post("/api/meetings/draft", json={
        "raw_text": "x", "meeting_date": "2026-06-09", "title": "生效会议",
        "channel_name": "测试群", "action_items": [
            {"title": "生效任务", "assignee_name": "吕彦", "priority": "medium", "due_date": "2026-06-15", "checkpoints": []}
        ]
    })
    meeting_id = draft_resp.json()["meeting_id"]
    await seeded_client.put(f"/api/meetings/{meeting_id}/activate")
    resp = await seeded_client.get("/api/actions")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# === 确认生效 ===

@pytest.mark.asyncio
async def test_activate_meeting(seeded_client):
    draft_resp = await seeded_client.post("/api/meetings/draft", json={
        "raw_text": "x", "meeting_date": "2026-06-09", "title": "会议",
        "channel_name": "测试群", "action_items": [
            {"title": "任务", "assignee_name": "吕彦", "priority": "high", "due_date": "2026-06-15", "checkpoints": []}
        ]
    })
    meeting_id = draft_resp.json()["meeting_id"]
    resp = await seeded_client.put(f"/api/meetings/{meeting_id}/activate")
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"


@pytest.mark.asyncio
async def test_activate_already_active(seeded_client):
    draft_resp = await seeded_client.post("/api/meetings/draft", json={
        "raw_text": "x", "meeting_date": "2026-06-09", "title": "会议",
        "channel_name": "测试群", "action_items": []
    })
    meeting_id = draft_resp.json()["meeting_id"]
    await seeded_client.put(f"/api/meetings/{meeting_id}/activate")
    resp = await seeded_client.put(f"/api/meetings/{meeting_id}/activate")
    assert resp.status_code == 400


# === 行动项编辑 ===

@pytest.mark.asyncio
async def test_update_action_item(seeded_client):
    draft_resp = await seeded_client.post("/api/meetings/draft", json={
        "raw_text": "x", "meeting_date": "2026-06-09", "title": "会议",
        "channel_name": "测试群", "action_items": [
            {"title": "原标题", "assignee_name": "吕彦", "priority": "medium", "due_date": "2026-06-15",
             "checkpoints": [{"check_date": "2026-06-12", "description": "检查"}]}
        ]
    })
    meeting_id = draft_resp.json()["meeting_id"]
    item_id = draft_resp.json()["action_items"][0]["id"]

    resp = await seeded_client.put(f"/api/meetings/{meeting_id}/items/{item_id}", json={
        "due_date": "2026-06-18",
        "watcher_name": "文静",
        "checkpoints": [
            {"check_date": "2026-06-14", "description": "新检查点"},
            {"check_date": "2026-06-16", "description": "二次检查"}
        ]
    })
    assert resp.status_code == 200

    # 验证修改生效
    edit_resp = await seeded_client.get(f"/api/meetings/{meeting_id}/edit")
    item = edit_resp.json()["action_items"][0]
    assert item["due_date"] == "2026-06-18"
    assert item["watcher_name"] == "文静"
    assert len(item["checkpoints"]) == 2
    assert item["confirmed"] == 1  # 修改保存即确认


@pytest.mark.asyncio
async def test_update_action_item_assignee_syncs_assignee_id(seeded_client):
    draft_resp = await seeded_client.post("/api/meetings/draft", json={
        "raw_text": "x", "meeting_date": "2026-06-09", "title": "会议",
        "channel_name": "测试群", "action_items": [
            {"title": "任务", "assignee_name": "吕彦", "priority": "medium", "due_date": "2026-06-15", "checkpoints": []}
        ]
    })
    meeting_id = draft_resp.json()["meeting_id"]
    item_id = draft_resp.json()["action_items"][0]["id"]

    resp = await seeded_client.put(f"/api/meetings/{meeting_id}/items/{item_id}", json={
        "assignee_name": "青哥"
    })
    assert resp.status_code == 200

    edit_resp = await seeded_client.get(f"/api/meetings/{meeting_id}/edit")
    item = edit_resp.json()["action_items"][0]
    assert item["assignee_name"] == "青哥"
    assert item["assignee_id"] == 3


@pytest.mark.asyncio
async def test_confirm_action_item(seeded_client):
    draft_resp = await seeded_client.post("/api/meetings/draft", json={
        "raw_text": "x", "meeting_date": "2026-06-09", "title": "会议",
        "channel_name": "测试群", "action_items": [
            {"title": "任务", "assignee_name": "青哥", "priority": "high", "due_date": "2026-06-15", "checkpoints": []}
        ]
    })
    meeting_id = draft_resp.json()["meeting_id"]
    item_id = draft_resp.json()["action_items"][0]["id"]

    resp = await seeded_client.put(f"/api/meetings/{meeting_id}/items/{item_id}/confirm")
    assert resp.status_code == 200

    edit_resp = await seeded_client.get(f"/api/meetings/{meeting_id}/edit")
    assert edit_resp.json()["action_items"][0]["confirmed"] == 1


@pytest.mark.asyncio
async def test_update_nonexistent_item(seeded_client):
    resp = await seeded_client.put("/api/meetings/999/items/999", json={"title": "x"})
    assert resp.status_code == 404


# === 行动项CRUD ===

@pytest.mark.asyncio
async def test_action_status_update(seeded_client):
    draft_resp = await seeded_client.post("/api/meetings/draft", json={
        "raw_text": "x", "meeting_date": "2026-06-09", "title": "会议",
        "channel_name": "测试群", "action_items": [
            {"title": "任务", "assignee_name": "吕彦", "priority": "high", "due_date": "2026-06-15", "checkpoints": []}
        ]
    })
    item_id = draft_resp.json()["action_items"][0]["id"]

    resp = await seeded_client.put(f"/api/actions/{item_id}", json={"status": "in_progress"})
    assert resp.status_code == 200

    resp = await seeded_client.put(f"/api/actions/{item_id}", json={"status": "done"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_feedback_submission(seeded_client):
    draft_resp = await seeded_client.post("/api/meetings/draft", json={
        "raw_text": "x", "meeting_date": "2026-06-09", "title": "会议",
        "channel_name": "测试群", "action_items": [
            {"title": "任务", "assignee_name": "吕彦", "priority": "high", "due_date": "2026-06-15", "checkpoints": []}
        ]
    })
    item_id = draft_resp.json()["action_items"][0]["id"]

    resp = await seeded_client.post(f"/api/actions/{item_id}/feedback", json={
        "content": "已完成50%", "progress": 50
    })
    assert resp.status_code == 200

    fb_resp = await seeded_client.get(f"/api/actions/{item_id}/feedbacks")
    assert len(fb_resp.json()) == 1
    assert fb_resp.json()[0]["progress"] == 50


@pytest.mark.asyncio
async def test_feedback_100_marks_done(seeded_client):
    draft_resp = await seeded_client.post("/api/meetings/draft", json={
        "raw_text": "x", "meeting_date": "2026-06-09", "title": "会议",
        "channel_name": "测试群", "action_items": [
            {"title": "任务", "assignee_name": "吕彦", "priority": "high", "due_date": "2026-06-15", "checkpoints": []}
        ]
    })
    item_id = draft_resp.json()["action_items"][0]["id"]
    meeting_id = draft_resp.json()["meeting_id"]
    await seeded_client.put(f"/api/meetings/{meeting_id}/activate")

    await seeded_client.post(f"/api/actions/{item_id}/feedback", json={"content": "全部完成", "progress": 100})

    actions_resp = await seeded_client.get("/api/actions")
    item = next(a for a in actions_resp.json() if a["id"] == item_id)
    assert item["status"] == "done"


# === Dashboard ===

@pytest.mark.asyncio
async def test_dashboard(seeded_client):
    draft_resp = await seeded_client.post("/api/meetings/draft", json={
        "raw_text": "x", "meeting_date": "2026-06-09", "title": "会议",
        "channel_name": "测试群", "action_items": [
            {"title": "任务1", "assignee_name": "吕彦", "priority": "high", "due_date": "2026-06-15", "checkpoints": []},
            {"title": "任务2", "assignee_name": "青哥", "priority": "medium", "due_date": "2026-06-20", "checkpoints": []}
        ]
    })
    await seeded_client.put(f"/api/meetings/{draft_resp.json()['meeting_id']}/activate")
    resp = await seeded_client.get("/api/actions/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert data["done"] == 0


@pytest.mark.asyncio
async def test_focus_owner_filter(seeded_client):
    draft_resp = await seeded_client.post("/api/meetings/draft", json={
        "raw_text": "x", "meeting_date": "2026-06-09", "title": "会议",
        "channel_name": "测试群", "action_items": [
            {"title": "文静关注任务", "assignee_name": "吕彦", "watcher_name": "文静", "priority": "medium", "due_date": "2026-07-10", "checkpoints": []},
            {"title": "高优任务", "assignee_name": "青哥", "priority": "high", "due_date": "2026-07-10", "checkpoints": []},
            {"title": "普通任务", "assignee_name": "青哥", "priority": "low", "due_date": "2026-07-10", "checkpoints": []}
        ]
    })
    await seeded_client.put(f"/api/meetings/{draft_resp.json()['meeting_id']}/activate")
    resp = await seeded_client.get("/api/actions", params={"focus_owner": "文静"})
    assert resp.status_code == 200
    titles = [item["title"] for item in resp.json()]
    assert "文静关注任务" in titles
    assert "高优任务" in titles
    assert "普通任务" not in titles


# === 文件上传 ===

@pytest.mark.asyncio
async def test_upload_txt_file(client):
    content = "会议纪要内容\n1.张三完成报告".encode("utf-8")
    resp = await client.post("/api/meetings/upload-file", files={"file": ("test.txt", content, "text/plain")})
    assert resp.status_code == 200
    assert "会议纪要内容" in resp.json()["text"]


@pytest.mark.asyncio
async def test_upload_unsupported_format(client):
    resp = await client.post("/api/meetings/upload-file", files={"file": ("test.xyz", b"data", "application/octet-stream")})
    assert resp.status_code == 400


# === 健康检查 ===

@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
