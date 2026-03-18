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

DOMAIN_ITEM_ATTRIBUTES = {
    "course": ["name", "category", "difficulty", "credits", "price", "teacher", "workload"],
    "shopping": ["name", "category", "price", "calories", "protein", "brand", "weight"],
    "travel": ["name", "category", "cost", "duration", "crowd_level", "location", "rating"],
    "workforce": ["name", "hourly_cost", "skill", "experience", "department", "reliability", "overtime_capacity"],
    "meal": ["name", "calories", "protein", "price", "cuisine", "chef", "spiciness"],
    "pc_build": ["name", "category", "price", "performance", "power", "brand", "compatibility"],
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
    current_target_tool = "get_current_target_slot"
    previous_target_tool = "get_previous_target_slot"
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
        f"{partial_repr}\n\n"
        "You must follow the hidden-slot path in order.\nOnly the current target hidden slot may be queried, checked, or filled next. "
        "To roll back, you may clear the immediately previous hidden slot with `set_slot`."
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
    item_attributes = DOMAIN_ITEM_ATTRIBUTES.get(domain, ["name"])
    item_attributes_text = ", ".join(item_attributes)
    return "\n".join(
        [
            domain_intro,
            "Follow the task policy exactly.",
            f"Each item in this domain has attributes such as: {item_attributes_text}.",
            "Use tools to inspect the current grid, reason about candidate ids, and update slots.",
            "Work through the hidden slots strictly in path order. Focus on one hidden slot at a time, gather evidence for that slot, place a candidate, validate it, and only then move to the next hidden slot in the path.",
            "Assume all pre-filled non-null slots are already correct, valid, and fixed.",
            "You must make sure the final solution satisfies every hidden-slot constraint and the global constraints.",
            "Never change pre-filled non-null slots unless a tool result or task policy clearly requires it.",
            "Your goal is to produce a fully filled grid that satisfies all constraints.",
        ]
    )


def build_tool_usage_instruction(task: Any) -> str:
    domain = getattr(task.dataset_object, "domain", "course")
    multi_attr_tool = f"get_{domain}_item_attributes"
    slot_tool = f"check_{domain}_slot_constraints"
    global_tool = f"check_{domain}_global_constraints"
    current_target_tool = "get_current_target_slot"
    previous_target_tool = "get_previous_target_slot"
    max_query_ids = getattr(task, "max_query_ids", 5)
    max_query_fields = getattr(task, "max_query_fields", 6)
    guidance_lines = [
        "Use the available tools instead of pretending to know hidden slot values.",
        f"Follow the hidden-slot path in order and complete the hidden slots one by one. Use `{current_target_tool}` to get the current hidden slot position, use `{previous_target_tool}` to get the previous hidden slot position when needed, and use `set_slot` to update the current hidden slot or clear the immediately previous hidden slot.",
        f"Each hidden slot has multiple options. Your choice for each slot must satisfy the corresponding slot constraints, and the completed grid must satisfy the global constraints. Use `{slot_tool}` when needed for any filled hidden slot, and use `{global_tool}` after all slots are filled.",
        f"Use the single-item info tool when you need all attributes for one item id. Use `{multi_attr_tool}` when you want up to {max_query_fields} selected attributes for up to {max_query_ids} item ids at once.",
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
