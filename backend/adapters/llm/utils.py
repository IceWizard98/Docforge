import json
import logging
import re

logger = logging.getLogger(__name__)


def extract_json(text: str) -> dict:
    """Extract JSON dict from LLM response text.

    Handles: markdown fences, trailing text, preamble text.
    Raises ValueError if no valid JSON dict can be extracted.
    """
    text = text.strip()

    # 1. Direct parse
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # 2. Extract from ```json ... ``` or ``` ... ``` fences
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if fence_match:
        try:
            result = json.loads(fence_match.group(1).strip())
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    # 3. Find first { to last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            result = json.loads(candidate)
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    preview = text[:300].replace("\n", "\\n")
    logger.error("Could not extract JSON from response: %s", preview)
    raise ValueError("Could not extract valid JSON from LLM response")


def extract_action_from_reply(text: str) -> dict | None:
    """Try to extract an action JSON (with 'type' and 'params' fields) from reply text.

    Handles cases where the LLM places the action structure inside the 'reply'
    text field instead of the structured 'action' field.
    Returns the parsed action dict if found, None otherwise.
    """
    try:
        data = extract_json(text)
        if isinstance(data, dict) and "type" in data and "params" in data:
            return data
    except ValueError:
        pass

    # Try to find a nested 'action' field inside the extracted JSON
    try:
        data = extract_json(text)
        if isinstance(data, dict):
            action = data.get("action")
            if isinstance(action, dict) and "type" in action:
                return action
    except ValueError:
        pass

    return None
