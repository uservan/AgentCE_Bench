import json
import logging
import time
from typing import Any, Optional
import copy
from litellm import completion

from .agent_tools_parse import parse_tool_calls
from .run_result import RunResult
from .utils import get_response_cost, get_response_usage
from .task import Task

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 3
ALLOW_SONNET_THINKING = False


class Agent:
    """一个轻量的 agent：接收 task，组装 messages，并完成生成。"""

    def __init__(self, model: str, **agent_params):
        self.model = model
        self.agent_params = agent_params
        logger.info("Agent initialized with model: %s", model)

    def generate(
        self,
        task: Task,
        **kwargs: Any,
    ) -> RunResult:
        """
        根据 task 组装消息并调用模型；如果触发工具，则执行工具并继续生成。
        参数基本从 task 获取，kwargs 保留以便后续扩展。
        """
        if "seed" not in kwargs and task.seed is not None:
            kwargs["seed"] = task.seed

        tool_schemas = task.get_tool_schemas()
        litellm_messages = task.build_initial_messages()

        request_params = {**self.agent_params, **kwargs}
        if request_params.get("num_retries") is None:
            request_params["num_retries"] = DEFAULT_MAX_RETRIES
        if self.model.startswith("claude") and not ALLOW_SONNET_THINKING:
            request_params["thinking"] = {"type": "disabled"}
        if tool_schemas and request_params.get("tool_choice") is None:
            request_params["tool_choice"] = "auto"

        total_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost": 0.0,
            "time": 0.0,
            "tool_calls_num": 0,
            "step_num": 0,
        }
        step_count = 0
        raw_messages = []
        status = "succeed"
        reason: Optional[str] = None

        start_time = time.perf_counter()
        try:
            while True:
                if step_count >= task.max_steps:
                    status = "error"
                    reason = "Max steps reached for task"
                    logger.warning("Max steps reached for task: %s", getattr(task.dataset_object, "instance_id", ""))
                    break
                if task.is_finished(litellm_messages[-2:]):
                    break
                try:
                    response = completion(
                        model=self.model,
                        messages=litellm_messages,
                        tools=tool_schemas,
                        **request_params,
                    )
                except Exception as e:
                    logger.error(e)
                    raise e
                step_count += 1
                cost = get_response_cost(response)
                usage = get_response_usage(response)
                total_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
                total_usage["completion_tokens"] += usage.get("completion_tokens", 0)
                total_usage["total_tokens"] += usage.get("total_tokens", 0)
                total_usage["cost"] += cost

                response = response.choices[0]
                self._append_raw_message(
                    raw_messages,
                    kind="model_response",
                    message=response.to_dict(),
                )
                response_message = response.message
                finish_reason = None
                try:
                    finish_reason = response.finish_reason
                    if finish_reason == "length":
                        logger.warning("Output was truncated due to token limit")
                except Exception as e:
                    logger.error(e)
                    raise e
                assert response_message.role == "assistant", ("The response should be an assistant message")

                assistant_content = (
                        (getattr(response_message, "reasoning_content", None) or "") + ""
                        + (getattr(response_message, "content", None) or "")
                    ).strip()
                assistant_message = {
                    "role": "assistant",
                    "content": assistant_content,
                    "tool_calls": None
                }
                litellm_messages.append(assistant_message)
                if finish_reason == "length":
                    max_tokens = request_params.get("max_tokens")
                    max_tokens_text = (
                        f"max_tokens={max_tokens}"
                        if max_tokens is not None
                        else "the configured token limit"
                    )
                    litellm_messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"Your previous response was truncated due to {max_tokens_text}. "
                                "Do not assume any unfinished tool call was executed. "
                                "Please continue from where you stopped and re-issue any tool call in full if needed."
                            ),
                        }
                    )
                    continue
                else:
                    parsed_tool_calls = parse_tool_calls(self.model, response_message)
                    normalized_tool_calls = []
                    if parsed_tool_calls:
                        assistant_message["tool_calls"] = [
                            {
                                "id": f"tool_call_{step_count}_{index}",
                                "type": "function",
                                "function": {
                                    "name": tool_call["name"],
                                    "arguments": tool_call["arguments"],
                                },
                            }
                            for index, tool_call in enumerate(parsed_tool_calls, start=1)
                        ]
                        normalized_tool_calls = assistant_message["tool_calls"]
                    raw_r = []
                    for tool_call in normalized_tool_calls:
                        tool_name = tool_call["function"]["name"]
                        try:
                            tool_args = json.loads(tool_call["function"]["arguments"] or "{}")
                        except json.JSONDecodeError as e:
                            logger.warning("Tool %s arguments parse failed, skipping: %s", tool_name, e)
                            r = {
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "name": tool_name,
                                "content": f"Tool arguments parse failed (possibly truncated), skipping: {e}",
                            }
                            litellm_messages.append(r)
                            raw_r.append(r)
                            continue
                        tool_result = task.call_tool(tool_name, tool_args)
                        total_usage["tool_calls_num"] += 1
                        r = {
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "name": tool_name,
                                "content": self._stringify(tool_result),
                            }
                        litellm_messages.append(r)
                        raw_r.append(r)
                    if raw_r:
                        self._append_raw_message(
                            raw_messages,
                            kind="tool_message",
                            message=raw_r,
                        )
        except Exception as e:
            status = "error"
            reason = str(e)
            logger.error("Generate failed: %s", e)

        elapsed_time = time.perf_counter() - start_time
        total_usage["time"] = elapsed_time
        total_usage["step_num"] = step_count
        return RunResult(
            task=task,
            content=litellm_messages,
            usage=total_usage,
            raw_messages=raw_messages,
            status=status,
            reason=reason,
        )

    def _build_messages(
        self,
        task: Any,
        messages: Optional[list[dict[str, Any]]] = None,
    ) -> list[dict[str, Any]]:
        """
        基于 BaseTask 的字段组装初始 messages。
        """
        if messages:
            return list(messages)

        if hasattr(task, "build_messages"):
            return task.build_messages()

        initial_state = getattr(task, "initial_state", {})
        system_prompt = self._build_system_prompt(task)
        user_prompt = self._build_user_prompt(task, initial_state)

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _build_system_prompt(self, task: Any) -> str:
        """
        根据工具定义生成 system prompt。
        """
        tools = getattr(task, "tools", []) or []
        tool_descs = []
        for tool in tools:
            if isinstance(tool, dict):
                if "function" in tool:
                    function_info = tool["function"]
                    tool_descs.append(
                        {
                            "name": function_info.get("name", ""),
                            "description": function_info.get("description", ""),
                            "parameters": function_info.get("parameters", {}),
                        }
                    )
                elif "name" in tool:
                    tool_descs.append(
                        {
                            "name": tool.get("name", ""),
                            "description": tool.get("description", ""),
                            "parameters": tool.get("parameters", {}),
                        }
                    )
            elif hasattr(tool, "openai_schema"):
                function_info = tool.openai_schema.get("function", {})
                tool_descs.append(
                    {
                        "name": function_info.get("name", ""),
                        "description": function_info.get("description", ""),
                        "parameters": function_info.get("parameters", {}),
                    }
                )

        if not tool_descs:
            return "You are a helpful assistant."

        return (
            "You are a helpful assistant.\n"
            "You can use the following tools when needed:\n"
            f"{json.dumps(tool_descs, ensure_ascii=False)}"
        )

    def _build_user_prompt(
        self,
        task: Any,
        initial_state: Any,
    ) -> str:
        """
        user prompt 只包含任务初始状态或任务描述。
        """
        if isinstance(initial_state, str):
            return initial_state
        return json.dumps(initial_state, ensure_ascii=False)

    def _get_tool_schemas(self, task: Any) -> Optional[list[dict[str, Any]]]:
        tools = getattr(task, "tools", None)
        if not tools:
            return None

        schemas = []
        for tool in tools:
            if hasattr(tool, "openai_schema"):
                schemas.append(tool.openai_schema)
            elif isinstance(tool, dict):
                if "type" in tool and "function" in tool:
                    schemas.append(tool)
                elif "name" in tool:
                    schemas.append(
                        {
                            "type": "function",
                            "function": {
                                "name": tool["name"],
                                "description": tool.get("description", ""),
                                "parameters": tool.get(
                                    "parameters",
                                    {"type": "object", "properties": {}},
                                ),
                            },
                        }
                    )
        return schemas or None

    def _stringify(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return str(value)

    def _append_raw_message(
        self,
        raw_messages: list[dict[str, Any]],
        kind: str,
        message: dict[str, Any],
    ) -> None:
        raw_messages.append(
            {
                "kind": kind,
                "message": copy.deepcopy(message),
                "timestamp": time.perf_counter(),
            }
        )


