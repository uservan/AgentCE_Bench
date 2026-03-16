import re
from loguru import logger
from litellm import ModelResponse, Usage, completion_cost
from typing import Any, Optional

def _parse_ft_model_name(model: str) -> str:
    """
    Parse the ft model name from the litellm model name.
    e.g: "ft:gpt-4.1-mini-2025-04-14:sierra::BSQA2TFg" -> "gpt-4.1-mini-2025-04-14"
    """
    pattern = r"ft:(?P<model>[^:]+):(?P<provider>\w+)::(?P<id>\w+)"
    match = re.match(pattern, model)
    if match:
        return match.group("model")
    else:
        return model

def get_response_cost(response: ModelResponse) -> float:
    """
    Get the cost of the response from the litellm completion.
    """
    response.model = _parse_ft_model_name(
        response.model
    )  # FIXME: Check Litellm, passing the model to completion_cost doesn't work.
    try:
        cost = completion_cost(completion_response=response)
    except Exception as e:
        # logger.error(e)
        return 0.0
    return cost


# def get_response_usage(response: ModelResponse) -> Optional[dict]:
#     usage: Optional[Usage] = response.get("usage")
#     if usage is None:
#         return None
#     return {
#         "completion_tokens": usage.completion_tokens,
#         "prompt_tokens": usage.prompt_tokens,
#     }

def get_response_usage(response: ModelResponse) -> dict[str, Any]:
    try:
        usage = getattr(response, "usage", None)
        if usage is None:
            return {}
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        total_tokens = getattr(
            usage,
            "total_tokens",
            prompt_tokens + completion_tokens,
        )
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
    except Exception as e:
        logger.warning("Could not extract usage information: %s", e)
        return {}