import json
from typing import Any, Dict
from src.utils.cache_helper import get_cached_output
from src.core.tools import query_mcp_registry


def resolve_capability(capability_query: str, tool_args: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Determine best action for a capability query.

    Returns
    -------
    dict with keys:
        action: 'use_cache' | 'use_mcp' | 'create_new_tool'
        data: varies by action
    """
    tool_args = tool_args or {}

    # 1. Cache lookup
    cache = get_cached_output.invoke({
        "tool_name": capability_query.replace(" ", "_").lower()[:40],  # naive mapping
        "input_signature": tool_args,
    })
    cache_str = str(cache)
    if not cache_str.startswith("[CacheMiss]") and not cache_str.startswith("[Error]"):
        return {"action": "use_cache", "data": cache_str}

    # 2. MCP registry
    matches = query_mcp_registry.invoke({"capability_query": capability_query})
    if matches and isinstance(matches, list):
        tool = matches[0]
        return {"action": "use_mcp", "data": tool}

    # 3. Need new tool
    return {"action": "create_new_tool", "data": None} 