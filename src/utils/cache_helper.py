from langchain_core.tools import tool
import os, json, hashlib

CACHE_BASE_DIR = os.path.join(os.getcwd(), ".prisma", "cache")


def _signature_hash(input_signature: dict) -> str:
    """Create the same 16-char hash used when caching outputs."""
    sig_source = json.dumps(input_signature or {}, sort_keys=True)
    return hashlib.sha256(sig_source.encode()).hexdigest()[:16]


@tool
def get_cached_output(tool_name: str, input_signature: dict | None = None) -> str:
    """Retrieve a previously cached output for a tool call.

    Args:
        tool_name: Name of the tool (directory under .prisma/cache).
        input_signature: The exact arguments dict that was passed when the tool was executed.
                         Must match the signature used during caching.
    Returns:
        The cached output string if present, or a descriptive cache-miss message.
    """
    if not tool_name:
        return "[Error] tool_name is required"

    sig_hash = _signature_hash(input_signature or {})
    cache_file = os.path.join(CACHE_BASE_DIR, tool_name, f"{sig_hash}.txt")

    if not os.path.exists(cache_file):
        return "[CacheMiss] No cached output for this tool/arguments combination."

    try:
        with open(cache_file, "r", encoding="utf-8") as fh:
            return fh.read()
    except Exception as e:
        return f"[Error] Failed to read cache: {e}" 