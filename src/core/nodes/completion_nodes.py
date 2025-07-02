"""
Completion nodes for the CodeReAct workflow.
Handles task finishing, review, and failure handling.
"""

from typing import Dict
from langchain_core.messages import AIMessage

from src.types import AgentState
from src.core.workflow_helpers import WorkflowHelpers
from src.core.tools import detect_finish


class CompletionNodes:
    """Nodes responsible for workflow completion and review."""
    
    def __init__(self, helpers: WorkflowHelpers):
        self.helpers = helpers
    
    def finish_node(self, state: AgentState) -> Dict:
        """Finish current subtask."""
        print("✅ Finishing subtask...")
        
        if state.get("messages"):
            final_content = state["messages"][-1].content
        else:
            results = state.get("subtask_results", [])
            final_content = results[-1] if results else "[No output]"
        
        current_idx = state.get("current_subtask_idx", 0)
        subtasks = state.get("subtasks", [])
        next_idx = current_idx + 1
        has_more = next_idx < len(subtasks)
        
        # Log completion of current subtask
        self.helpers.log_event(state["run_id"], "subtask_completed", {"index": current_idx})
        
        print(f"🔍 Subtask {current_idx} completed. Has more: {has_more} (next: {next_idx}/{len(subtasks)})")
        
        if isinstance(final_content, str):
            pass
        
        if isinstance(final_content, str) and final_content.startswith("[Error]"):
            answer = f"Error: {final_content}"
        else:
            results = state.get("subtask_results", [])
            if len(results) > 1:
                answer = f"Combined results:\n" + "\n---\n".join(results)
            else:
                answer = final_content
        
        self.helpers.save_artifact(state["run_id"], "final_answer.txt", answer)
        
        # CRITICAL FIX: Only increment index if there are more subtasks
        updates = {
            "final_answer": answer,
            "has_more_subtasks": has_more,
            "messages": [AIMessage(content=f"Completed: {answer}")],
            "current_subtask_failure_count": 0  # Reset failure count for next subtask
        }
        
        # Only increment if we have more subtasks to prevent infinite loop
        if has_more:
            updates["current_subtask_idx"] = next_idx
            print(f"🔄 Moving to next subtask: {next_idx}")
        else:
            print("🏁 All subtasks completed - staying at current index")
        
        return updates
    
    def review_node(self, state: AgentState) -> Dict:
        """Review final answer quality."""
        print("🎯 Reviewing answer...")
        
        answer_text = state.get("final_answer", "")
        try:
            review = detect_finish.invoke({
                "original_request": state["original_query"],
                "current_answer": answer_text
            })
            passed = isinstance(review, dict) and review.get("finish", False)
        except Exception:
            passed = True  # Default to accepting answer
        
        retry_count = state.get("review_retry_count", 0)
        if not passed:
            retry_count += 1
        else:
            retry_count = 0
        
        self.helpers.log_event(state["run_id"], "review_completed", {"passed": passed})
        
        return {
            "review_passed": passed,
            "review_retry_count": retry_count
        }
    
    def fail_node(self, state: AgentState) -> Dict:
        """Handle workflow failure."""
        print("❌ Workflow failed")
        
        error = state.get("validation_error", "Unknown error")
        current_failures = state.get("current_subtask_failure_count", 0) + 1
        
        # Check if current subtask has failed too many times
        if current_failures >= 3:
            print(f"🛑 Subtask failed {current_failures} times - terminating workflow")
            self.helpers.log_event(state["run_id"], "subtask_max_failures_reached", {
                "subtask_idx": state.get("current_subtask_idx", 0),
                "failure_count": current_failures,
                "error": error
            })
            
            return {
                "messages": [AIMessage(content=f"Subtask failed after {current_failures} attempts. Terminating workflow.")],
                "final_answer": f"Error: Subtask failed after maximum retries ({current_failures}). Last error: {error}",
                "has_more_subtasks": False,  # Force workflow termination
                "current_subtask_failure_count": current_failures
            }
        else:
            print(f"⚠️ Subtask failure {current_failures}/3 - will retry")
            self.helpers.log_event(state["run_id"], "subtask_failure", {
                "subtask_idx": state.get("current_subtask_idx", 0),
                "failure_count": current_failures,
                "error": error
            })
            
            return {
                "messages": [AIMessage(content=f"Subtask failed (attempt {current_failures}/3): {error}")],
                "current_subtask_failure_count": current_failures,
                "validation_error": error  # Keep the error for retry logic
            } 