"""
Decision engine for the CodeReAct workflow system.
Contains all conditional logic for routing between workflow nodes.
"""

from src.types import AgentState


class DecisionEngine:
    """Handles all conditional routing decisions in the workflow."""
    
    MAX_RETRIES = 3
    
    @staticmethod
    def decide_resolution(state: AgentState) -> str:
        """Decide how to resolve capability."""
        action = state.get("resolve_action", "create")
        mapping = {"use_cache": "cache", "use_mcp": "existing"}
        return mapping.get(action, "create")
    
    @staticmethod
    def decide_generation(state: AgentState) -> str:
        """Decide after code generation."""
        if state.get("validation_error"):
            return "fail"
        if state.get("need_more_research"):
            return "research"
        return "validate"
    
    @classmethod
    def decide_validation(cls, state: AgentState) -> str:
        """Decide after validation."""
        if state.get("validation_passed"):
            return "register"
        
        retry_count = state.get("generation_retry_count", 0)
        if retry_count < cls.MAX_RETRIES:
            return "retry"
        
        return "fail"
    
    @staticmethod
    def decide_brainstorm(state: AgentState) -> str:
        """Decide after brainstorming."""
        if state.get("validation_error"):
            return "fail"
        return "continue"
    
    @staticmethod
    def decide_prepare_args(state: AgentState) -> str:
        """Decide after preparing arguments."""
        if state.get("validation_error"):
            return "fail"
        return "execute"
    
    @staticmethod
    def decide_finish(state: AgentState) -> str:
        """Decide after finishing subtask."""
        # Check if current subtask failed too many times
        if state.get("current_subtask_failure_count", 0) >= 3:
            return "end"  # Terminate workflow due to max failures
        
        if state.get("has_more_subtasks"):
            return "next"
        return "review"
    
    @staticmethod
    def decide_review(state: AgentState) -> str:
        """Decide after reviewing results."""
        if state.get("review_passed"):
            return "end"
        # If review failed too many times, fail gracefully instead of infinite looping
        if state.get("review_retry_count", 0) >= 3:
            return "fail"
        return "plan"
    
    @staticmethod
    def decide_failure(state: AgentState) -> str:
        """Decide what to do after a subtask failure."""
        if state.get("current_subtask_failure_count", 0) >= 3:
            return "end"  # Terminate workflow
        return "retry" 