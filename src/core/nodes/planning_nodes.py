"""
Planning nodes for the CodeReAct workflow.
Handles task decomposition and subtask management.
"""

from typing import Dict
from src.types import AgentState, WorkflowStatus
from src.core.workflow_helpers import WorkflowHelpers
from src.prompts.template import get_prompt_template
from src.core.tools import request_user_input

class PlanningNodes:
    """Nodes responsible for planning and subtask management."""
    
    def __init__(self, helpers: WorkflowHelpers):
        self.helpers = helpers
    
    def plan_node(self, state: AgentState) -> Dict:
        """Plan subtasks for the query."""
        print("🧠 Planning subtasks...")
        
        query = state["original_query"]
        
        system_prompt = get_prompt_template("planner_subtasks")
        # system_prompt = """Break down the user query into structured subtasks.
        # Return a JSON array of objects with: id, description, capability_query, depends_on fields."""
        
        result, raw = self.helpers.llm_json_task(system_prompt, f"Query: {query}")
        
        if not result or not isinstance(result, list):
            print("⚠️ LLM didn't return valid JSON array, using fallback")
            print(f"🔍 LLM raw response: {raw[:500]}...")  # Show first 500 chars
            result = [{
                "id": 1,
                "description": query,
                "capability_query": query,
                "depends_on": [],
                "status": None,
                "result": None
            }]
        else:
            print(f"✅ Successfully created {len(result)} subtasks")
        
        # Ensure all subtasks have required fields
        for subtask in result:
            subtask.setdefault("status", None)
            subtask.setdefault("result", None)
        
        self.helpers.log_event(state["run_id"], "plan_created", result)
        
        return {
            "status": WorkflowStatus.PLANNING,
            "subtasks": result,
            "current_subtask_idx": 0,
            "active_query": result[0]["capability_query"],
            "subtask_results": []
        }
    
    def maybe_request_user_input_node(self, state: AgentState) -> Dict:
        """If in interactive mode, maybe ask the user for input."""
        if not self.helpers.is_interactive:
            return {}

        print("🤔 Checking if user input is needed...")

        # Create a lean version of the state for the prompt
        prompt_state = {
            "original_query": state.get("original_query"),
            "subtasks": state.get("subtasks"),
            "subtask_results": state.get("subtask_results", [])
        }

        system_prompt = """You are an assistant helping a user. Your goal is to decide if you should ask a clarifying question.
Given the user's original query and the current plan, do you need to ask for more information?

- If the plan seems good and you have enough information to proceed, respond with only the word "continue".
- If you are unsure about something or need more details, ask a single, clear question.

Examples:
- If the plan is to "search for houses" but the location is missing, a good question is "What city are you looking for houses in?"
- If the plan looks solid, just respond "continue".
"""
        user_input = f"Current state: {prompt_state}"

        # We don't need a JSON task here, a simple text response is fine.
        chain = self.helpers.llm.with_config({"tags": ["interactive_check"]})
        response = chain.invoke(f"{system_prompt}\n\n{user_input}")
        answer = response.content.strip()

        if answer.lower() != "continue":
            print(f"❓ Asking user for input: {answer}")
            user_response = request_user_input.invoke({"question": answer})
            print(f"🗣️ User responded: {user_response}")
            # Add the user's response to the shared memory or messages
            # The value for "messages" must be a list to be concatenated to the state.
            return {"messages": [self.helpers.create_message(f"User feedback: {user_response}", "user_feedback")]}

        print("✅ Plan looks good, continuing...")
        return {}
    
    def next_subtask_node(self, state: AgentState) -> Dict:
        """Load next subtask."""
        print("📋 Loading next subtask...")
        
        idx = state.get("current_subtask_idx", 0)
        subtasks = state.get("subtasks", [])
        
        # Debug logging to identify infinite loop
        print(f"🔍 Current subtask index: {idx}")
        print(f"🔍 Total subtasks: {len(subtasks) if subtasks else 0}")
        if subtasks and idx < len(subtasks):
            print(f"🔍 Current subtask: {subtasks[idx]['description']}")
        
        if not subtasks or idx >= len(subtasks):
            print("🏁 No more subtasks - workflow completed")
            return {
                "status": WorkflowStatus.COMPLETED,
                "has_more_subtasks": False
            }
        
        subtask = subtasks[idx]
        self.helpers.log_event(state["run_id"], "subtask_started", subtask)
        
        # Update subtask status
        if "status" in subtask:
            subtask["status"] = WorkflowStatus.RESOLVING
        
        return {
            "status": WorkflowStatus.RESOLVING,
            "active_query": subtask["capability_query"],
            "has_more_subtasks": True
        } 