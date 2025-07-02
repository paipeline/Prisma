"""
Workflow type definitions for the CodeReAct system.
"""

from typing import TypedDict, Optional, Dict, Any, List, Literal, Union
from dataclasses import dataclass

class WorkflowConfig(TypedDict):
    """Configuration for workflow execution."""
    max_retries: int
    max_subtasks: int
    recursion_limit: int
    enable_caching: bool
    enable_web_search: bool
    log_level: Literal["debug", "info", "warning", "error"]

class NodeResult(TypedDict):
    """Result from executing a workflow node."""
    success: bool
    data: Optional[Dict[str, Any]]
    error: Optional[str]
    next_node: Optional[str]
    state_updates: Optional[Dict[str, Any]]

class DecisionResult(TypedDict):
    """Result from a decision point in the workflow."""
    decision: str
    reason: Optional[str]
    confidence: Optional[float]
    metadata: Optional[Dict[str, Any]]

@dataclass
class WorkflowMetrics:
    """Metrics collected during workflow execution."""
    start_time: float
    end_time: Optional[float] = None
    total_nodes_executed: int = 0
    total_llm_calls: int = 0
    total_tool_calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    errors_encountered: int = 0
    retries_attempted: int = 0
    
    @property
    def duration(self) -> Optional[float]:
        """Calculate total execution duration."""
        if self.end_time is None:
            return None
        return self.end_time - self.start_time
    
    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total_cache_attempts = self.cache_hits + self.cache_misses
        if total_cache_attempts == 0:
            return 0.0
        return self.cache_hits / total_cache_attempts

class ExecutionContext(TypedDict):
    """Context for workflow execution."""
    config: WorkflowConfig
    metrics: WorkflowMetrics
    debug_mode: bool
    dry_run: bool 