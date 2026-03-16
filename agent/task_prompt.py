import json
from typing import Any

STOP_FUNCTION_NAME = "done"
STOP_TOKEN = "###STOP###"

DOMAIN_AGENT_INTROS = {
    "course": "You are solving a course schedule construction task.",
    "shopping": "You are solving a shopping plan construction task.",
    "travel": "You are solving a travel itinerary construction task.",
    "workforce": "You are solving a workforce scheduling task.",
    "meal": "You are solving a meal planning task.",
    "pc_build": "You are solving a PC build configuration task.",
}

BENCHMARK_SYSTEM_PROMPT = """
<instructions>
{agent_instruction}
</instructions>
<tool_usage>
{tool_usage}
</tool_usage>
<task_policy>
{task_policy}
</task_policy>
<task_goal>
{task_goal}
</task_goal>
""".strip()


def build_initial_messages(task: Any) -> list[dict[str, Any]]:
    """为 benchmark task 构建初始消息。"""
    system_content = BENCHMARK_SYSTEM_PROMPT.format(
        agent_instruction=build_agent_instruction(task),
        tool_usage=build_tool_usage_instruction(task),
        task_policy=task.dataset_object.task_instruction,
        task_goal=(
            "Complete the partially filled solution grid. "
            "Keep existing non-null entries unchanged and fill every null slot."
        ),
    )
    partial_repr = json.dumps(task.partial_solution, ensure_ascii=False)
    user_content = (
        "Here is the current partial solution grid.\n"
        "Each `null` value is a missing slot that still needs a valid item id.\n\n"
        f"{partial_repr}"
    )
    return [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content},
    ]


def build_agent_instruction(task: Any) -> str:
    domain = getattr(task.dataset_object, "domain", "")
    domain_intro = DOMAIN_AGENT_INTROS.get(
        domain,
        "You are solving a structured grid-completion task.",
    )
    return "\n".join(
        [
            domain_intro,
            "Follow the task policy exactly.",
            "Use tools to inspect the current grid, reason about candidate ids, and update slots.",
            "Never change pre-filled non-null slots unless a tool result or task policy clearly requires it.",
            "Your goal is to produce a fully filled grid that satisfies all constraints.",
        ]
    )


def build_tool_usage_instruction(task: Any) -> str:
    guidance_lines = [
        "Use the available tools instead of pretending to know hidden slot values.",
        "Use `set_slot` to fill or clear a slot in the grid.",
        "Use the available query or checking tools when you need to inspect the current state or validate progress.",
        f"When the grid is complete and you are satisfied with the result, call `{STOP_FUNCTION_NAME}`.",
        f"Your final action must be a single call to `{STOP_FUNCTION_NAME}` with no other tool calls in that message.",
    ]
    return "\n".join(guidance_lines)


def is_done_tool_message(message: dict[str, Any]) -> bool:
    if message.get("role") != "tool":
        return False
    if message.get("name") != STOP_FUNCTION_NAME:
        return False

    content = message.get("content", "")
    if isinstance(content, dict):
        payload = content
    else:
        try:
            payload = json.loads(content)
        except (TypeError, json.JSONDecodeError):
            payload = None

    return isinstance(payload, dict) and payload.get("messages") == STOP_TOKEN
