import json
import re
from typing import Any


TOOL_CALL_BLOCK_PATTERN = re.compile(
    r"<tool_call>\s*<function=([^>]+)>(.*?)</function>\s*</tool_call>",
    re.DOTALL,
)
PARAMETER_PATTERN = re.compile(
    r"<parameter=([^>]+)>\s*(.*?)\s*</parameter>",
    re.DOTALL,
)


def parse_tool_calls(model: str, response_message: Any) -> list[dict[str, str]]:
    normalized_model = model.lower()
    if "qwen3.5" in normalized_model or "qwen3_5" in normalized_model:
        parsed_tool_calls = _parse_direct_tool_calls(response_message)
        if parsed_tool_calls:
            return deduplicate_tool_calls(parsed_tool_calls)
        return deduplicate_tool_calls(
            _parse_qwen3_5_tool_calls(_build_message_text(response_message))
        )

    return deduplicate_tool_calls(_parse_direct_tool_calls(response_message))


def _parse_direct_tool_calls(response_message: Any) -> list[dict[str, str]]:
    parsed_tool_calls: list[dict[str, str]] = []
    for tool_call in getattr(response_message, "tool_calls", None) or []:
        function_info = getattr(tool_call, "function", None)
        tool_name = getattr(function_info, "name", None)
        arguments = getattr(function_info, "arguments", None)
        if not tool_name:
            continue
        if isinstance(arguments, str):
            arguments_str = arguments
        else:
            arguments_str = json.dumps(arguments or {}, ensure_ascii=False)
        parsed_tool_calls.append(
            {
                "name": str(tool_name),
                "arguments": arguments_str,
            }
        )
    return parsed_tool_calls


def _parse_qwen3_5_tool_calls(content: str) -> list[dict[str, str]]:
    parsed_tool_calls: list[dict[str, str]] = []
    for function_name, function_body in TOOL_CALL_BLOCK_PATTERN.findall(content):
        tool_args = {
            parameter_name.strip(): parameter_value.strip()
            for parameter_name, parameter_value in PARAMETER_PATTERN.findall(function_body)
        }
        parsed_tool_calls.append(
            {
                "name": function_name.strip(),
                "arguments": json.dumps(tool_args, ensure_ascii=False),
            }
        )
    return parsed_tool_calls


def deduplicate_tool_calls(tool_calls: list[dict[str, str]]) -> list[dict[str, str]]:
    deduplicated: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for tool_call in tool_calls:
        key = (tool_call.get("name", ""), tool_call.get("arguments", ""))
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(tool_call)
    return deduplicated




def _build_message_text(response_message: Any) -> str:
    return (
        (getattr(response_message, "reasoning_content", None) or "")
        + " "
        + (getattr(response_message, "content", None) or "")
    ).strip()
