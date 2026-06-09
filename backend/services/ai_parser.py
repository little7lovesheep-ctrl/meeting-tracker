import json
import anthropic
from config import ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, ANTHROPIC_MODEL

PARSE_SYSTEM_PROMPT = """你是一个会议纪要解析助手。从会议纪要文本中提取所有行动项。

输出严格JSON格式，不要输出其他内容：
{
  "meeting_title": "会议主题（从内容推断）",
  "action_items": [
    {
      "title": "行动项简述（一句话）",
      "description": "详细描述（如有补充信息）",
      "assignee_name": "责任人姓名",
      "due_date": "YYYY-MM-DD 或 null",
      "priority": "high/medium/low",
      "checkpoints": [
        {
          "check_date": "YYYY-MM-DD",
          "description": "检查什么内容"
        }
      ]
    }
  ]
}

规则：
1. 责任人提取原始姓名，保持会议中的称呼
2. 截止时间：如"本周""两周内"根据会议日期推算具体日期；无明确时间设为会议后7天
3. check节点：中间汇报点、确认点、阶段性验收点都提取为checkpoint
4. 如果一个大任务有多个子步骤但同一个责任人，拆分为多个action_item
5. 优先级：语气词"必须""紧急""本周"→high；一般→medium；"有空时""后续"→low
6. 忽略纯讨论性内容，只提取有明确执行动作的项
7. checkpoints的check_date要合理分布在截止日期之前"""


async def parse_meeting_notes(raw_text: str, meeting_date: str) -> dict:
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY 未配置，请设置环境变量")

    client_kwargs = {"api_key": ANTHROPIC_API_KEY}
    if ANTHROPIC_BASE_URL:
        client_kwargs["base_url"] = ANTHROPIC_BASE_URL

    client = anthropic.AsyncAnthropic(**client_kwargs)

    message = await client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=4096,
        system=PARSE_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"会议日期：{meeting_date}\n\n会议纪要内容：\n{raw_text}"
            }
        ]
    )

    response_text = message.content[0].text

    if "```" in response_text:
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        else:
            response_text = response_text.split("```")[1].split("```")[0]

    try:
        return json.loads(response_text.strip())
    except json.JSONDecodeError:
        raise ValueError(f"AI返回内容无法解析为JSON，请重试")
