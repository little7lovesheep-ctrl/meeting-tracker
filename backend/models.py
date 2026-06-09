from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


class UserCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    dingtalk_id: Optional[str] = None
    role: str = "member"
    password: Optional[str] = None


class UserOut(BaseModel):
    id: int
    name: str
    phone: Optional[str]
    dingtalk_id: Optional[str]
    role: str


class LoginRequest(BaseModel):
    name: str
    password: str


class MeetingCreate(BaseModel):
    raw_text: str
    meeting_date: Optional[date] = None
    title: Optional[str] = None
    channel_name: Optional[str] = None


class CheckpointOut(BaseModel):
    id: int
    check_date: str
    description: Optional[str]
    notified: bool


class ActionItemOut(BaseModel):
    id: int
    meeting_id: Optional[int]
    title: str
    description: Optional[str]
    assignee_id: Optional[int]
    assignee_name: Optional[str]
    status: str
    priority: str
    due_date: Optional[str]
    created_at: Optional[str]
    completed_at: Optional[str]
    checkpoints: List[CheckpointOut] = []


class ActionItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    assignee_id: Optional[int] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[date] = None


class FeedbackCreate(BaseModel):
    content: str
    progress: int = 0


class FeedbackOut(BaseModel):
    id: int
    action_item_id: int
    user_id: Optional[int]
    user_name: Optional[str] = None
    content: str
    progress: int
    created_at: Optional[str]
