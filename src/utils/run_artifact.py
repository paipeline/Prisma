import os
from typing import Any, List

from .event_logger import _ensure_run_dir  # Re-use the private helper for dir creation

ARTIFACTS_SUBDIR = "artifacts"

# -------------------------------------------------------------------------------------------------
# Artifacts: Persist arbitrary content under runs/<run_id>/artifacts/
# -------------------------------------------------------------------------------------------------

def _artifact_root(run_id: str) -> str:
    """Return the base artifact directory for a run and ensure it exists."""
    run_dir = _ensure_run_dir(run_id)
    art_dir = os.path.join(run_dir, ARTIFACTS_SUBDIR)
    os.makedirs(art_dir, exist_ok=True)
    return art_dir


def add_artifact(run_id: str, rel_path: str, data: bytes | str) -> str:
    """Persist arbitrary content under runs/<run_id>/artifacts/.

    Parameters
    ----------
    run_id : str
        The ID of the workflow run (same as used by event_logger).
    rel_path : str
        A path relative to the artifact root. Use forward-slash separators.
    data : bytes | str
        Content to be written. If str, it is encoded as UTF-8.

    Returns
    -------
    str
        Absolute path to the stored artifact on disk.
    """
    art_dir = _artifact_root(run_id)
    abs_path = os.path.join(art_dir, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)

    if isinstance(data, str):
        data = data.encode("utf-8", errors="replace")

    with open(abs_path, "wb") as fh:
        fh.write(data)

    return abs_path


def read_artifact(run_id: str, rel_path: str) -> bytes | None:
    """Read a previously stored artifact; returns None if missing."""
    art_dir = _artifact_root(run_id)
    abs_path = os.path.join(art_dir, rel_path)
    if not os.path.isfile(abs_path):
        return None
    with open(abs_path, "rb") as fh:
        return fh.read()


def list_artifacts(run_id: str) -> List[str]:
    """Return a list of artifact paths (relative to artifact root) for a run."""
    art_dir = _artifact_root(run_id)
    paths: List[str] = []
    for root, _, files in os.walk(art_dir):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, art_dir)
            paths.append(rel)
    return sorted(paths) 