# 货车宝会议关键事项追踪系统

会议纪要导入 → AI智能解析行动项 → 钉钉群推送确认 → 团队协作修改 → 定时提醒跟进

## 快速启动

### 环境要求
- Python 3.12+
- Node.js 18+

### 后端

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

配置 `backend/.env`：
```
ANTHROPIC_API_KEY=你的key
ANTHROPIC_BASE_URL=https://api.ccswitch.cc
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
JWT_SECRET=自定义密钥
```

启动：
```bash
.venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

### 一键启动（本地开发）

```bash
./start.sh
```

## 功能

- AI解析会议纪要（支持粘贴文本/上传 txt、md、docx、pdf）
- 解析结果推送到钉钉群，附带编辑链接
- 团队成员在线确认/修改自己的行动项
- 管理者审核后确认生效
- 工作日自动提醒：9:00今日待办、9:30逾期汇总、17:00明日到期预警
- 看板视图 + Dashboard全局统计

## 技术栈

- 后端：Python / FastAPI / SQLite / APScheduler
- 前端：Vue 3 / Vite / Pinia / Axios
- AI：Claude API（Sonnet）
- 推送：钉钉机器人 Webhook
