import os, json, datetime
from typing import Any

BASE_RUNS_DIR = os.path.join(os.getcwd(), "runs")


def _ensure_run_dir(run_id: str) -> str:
    """Ensure the directory for a given run exists and return path."""
    path = os.path.join(BASE_RUNS_DIR, run_id)
    os.makedirs(path, exist_ok=True)
    return path


def log_event(run_id: str, event_type: str, payload: Any) -> None:
    """Append a single JSONL event.

    Args:
        run_id: Unique id for the workflow run.
        event_type: Short string like "prompt_generated", "llm_response", "tool_call".
        payload: Any JSON-serialisable object with event details.
    """
    try:
        run_path = _ensure_run_dir(run_id)
        event_file = os.path.join(run_path, "events.jsonl")
        entry = {
            "ts": datetime.datetime.utcnow().isoformat(),
            "type": event_type,
            "payload": payload,
        }
        with open(event_file, "a", encoding="utf-8") as fh:
            json.dump(entry, fh)
            fh.write("\n")
    except Exception:
        # Logging should never crash the main workflow
        pass 