import os
import json
import datetime
from pathlib import Path
from typing import Any

class RunLogger:
    """Light-weight per-run logger.

    Each user query gets its own folder inside `logs/` (created at project root):
        logs/2025-06-27T11-30-59_query-slug/
            original_query.txt
            <arbitrary files logged by the workflow>
            final_answer.txt

    Other modules can call `log_text`, `log_json`, or `log_binary` to persist artefacts.
    """

    def __init__(self, query: str, base_dir: str | os.PathLike = None):
        timestamp = datetime.datetime.now().isoformat(timespec="seconds").replace(":", "-")
        slug = ("_".join(query.lower().split())[:40] or "query").replace("/", "_")
        self.base_dir = Path(base_dir or os.getcwd()) / "logs"
        self.run_dir = self.base_dir / f"{timestamp}_{slug}"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.log_text("original_query.txt", query)

    # ---------------------------------------------------------------------
    # Generic helpers
    # ---------------------------------------------------------------------
    def _safe_path(self, filename: str) -> Path:
        return self.run_dir / filename

    def log_text(self, filename: str, text: str):
        path = self._safe_path(filename)
        path.write_text(text, encoding="utf-8")

    def log_json(self, filename: str, data: Any):
        path = self._safe_path(filename)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)

    def log_binary(self, filename: str, blob: bytes):
        path = self._safe_path(filename)
        path.write_bytes(blob)

    # ---------------------------------------------------------------------
    # Convenience wrappers used by the workflow
    # ---------------------------------------------------------------------
    def log_prompt(self, prompt: str):
        self.log_text("prompt.txt", prompt)

    def log_final_answer(self, answer: str):
        self.log_text("final_answer.txt", answer)

    # Read-only helpers -----------------------------------------------------
    @property
    def run_id(self) -> str:
        return self.run_dir.name

    def as_dict(self):
        return {
            "run_id": self.run_id,
            "run_dir": str(self.run_dir),
        } 