from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from routers import auth, meetings, actions, users, channels
from services.scheduler import setup_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    setup_scheduler()
    yield


app = FastAPI(title="货车宝会议关键事项追踪", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(meetings.router)
app.include_router(actions.router)
app.include_router(users.router)
app.include_router(channels.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
