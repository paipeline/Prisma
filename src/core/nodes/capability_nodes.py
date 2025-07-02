"""
Capability nodes for the CodeReAct workflow.
Handles capability resolution, tool creation, and validation.
"""

import json
import re
from typing import Dict

from src.types import AgentState, WorkflowStatus
from src.core.workflow_helpers import WorkflowHelpers
from src.utils.capability_resolver import resolve_capability
from src.utils.mcp_helper import log_failure_pattern
from src.core.tools import script_generate, code_execute_local, insert_mcp

# --- Prompt Templates ---

# System prompt for brainstorming - separated from user input
BRAINSTORM_SYSTEM_PROMPT = """You are an expert API design specialist. Your job is to analyze capability requests and design appropriate tools.

CRITICAL INSTRUCTIONS:
1. You MUST respond with ONLY a valid JSON object
2. Do NOT include any explanatory text, markdown, or <think> blocks
3. The JSON must follow the exact schema provided below
4. Analyze the user's capability request and existing tools to determine if a new tool is needed

JSON SCHEMA:
{
  "name": "string (snake_case function name)",
  "description": "string (clear description of tool purpose)",
  "input_schema": {
    "type": "object",
    "properties": {
      "parameter_name": {"type": "string|number|boolean|array|object", "description": "string"}
    },
    "required": ["list_of_required_parameters"]
  },
  "output_schema": {
    "type": "object", 
    "properties": {
      "field_name": {"type": "string|number|boolean|array|object", "description": "string"}
    }
  },
  "required_packages": ["list_of_pip_packages"]
}

IMPORTANT: Your response must be ONLY the JSON object, nothing else."""

class CapabilityNodes:
    """Nodes responsible for capability resolution and tool creation."""
    
    def __init__(self, helpers: WorkflowHelpers):
        self.helpers = helpers
    
    def resolve_node(self, state: AgentState) -> Dict:
        """Resolve capability requirement."""
        print("🔍 Resolving capability...")
        
        capability = state["active_query"]
        result = resolve_capability(capability, {})
        
        updates = {"resolve_action": result["action"]}
        
        if result["action"] == "use_cache":
            cache_output = result["data"]
            updates.update({
                "cached_result": cache_output,
                "subtask_results": state.get("subtask_results", []) + [cache_output]
            })
            self.helpers.log_event(state["run_id"], "cache_hit", {"capability": capability})
            
        elif result["action"] == "use_mcp":
            tool_meta = result["data"]
            updates.update({
                "tool_name": tool_meta.get("name"),
                "tool_description": tool_meta.get("description"),
                "tool_input_schema": tool_meta.get("input"),
                "tool_output_schema": tool_meta.get("output"),
                "required_packages": tool_meta.get("packages", [])
            })
            self.helpers.log_event(state["run_id"], "mcp_selected", tool_meta)
        else:
            self.helpers.log_event(state["run_id"], "new_tool_needed", {"capability": capability})
        
        return updates
    
    def brainstorm_node(self, state: AgentState) -> Dict:
        """Brainstorm new tool design."""
        print("💡 Brainstorming tool design...")
        
        # Get available MCP tools for context
        try:
            from src.utils.mcp_helper import get_mcp_registry
            mcp_tools = get_mcp_registry()
            tool_list = "\n".join([f"- {tool.get('name', 'Unknown')}: {tool.get('description', 'No description')}" 
                                 for tool in mcp_tools]) if mcp_tools else "No existing tools"
        except Exception:
            tool_list = "Could not load MCP registry"
        
        # Construct proper user input with context
        user_input = f"""CAPABILITY REQUEST: {state['active_query']}

EXISTING TOOLS:
{tool_list}

TASK CONTEXT: {state.get('user_query', 'General capability request')}

Please analyze this capability request and design an appropriate tool following the JSON schema."""

        # Use proper parameter separation for llm_json_task
        try:
            result, raw = self.helpers.llm_json_task(BRAINSTORM_SYSTEM_PROMPT, user_input)
            
            # Robust error handling to prevent workflow failures
            if raw:
                # Clean any think blocks or extra text
                raw_clean = re.sub(r"<think>[\s\S]*?</think>", "", raw, flags=re.IGNORECASE).strip()
                if raw_clean != raw and not result:
                    result = self.helpers.extract_json(raw_clean)
                    raw = raw_clean

            # Additional extraction attempts
            if not isinstance(result, dict) and raw:
                result = self.helpers.extract_json(raw)

            # Handle list responses (take first item)
            if isinstance(result, list) and result:
                result = result[0] if isinstance(result[0], dict) else None

            # Validate result structure
            if not isinstance(result, dict):
                error_msg = f"Invalid brainstorm response format. Raw: {str(raw)[:300]}..."
                print(f"❌ {error_msg}")
                return self.helpers.handle_error(error_msg) | {
                    "status": WorkflowStatus.FAILED,
                    "messages": [self.helpers.create_message(error_msg, "brainstorm_error")]
                }
            
            # Validate required fields
            required_fields = ["name", "description", "input_schema", "output_schema"]
            missing_fields = [field for field in required_fields if not result.get(field)]
            if missing_fields:
                error_msg = f"Missing required fields: {missing_fields}"
                print(f"❌ {error_msg}")
                return self.helpers.handle_error(error_msg) | {
                    "status": WorkflowStatus.FAILED,
                    "messages": [self.helpers.create_message(error_msg, "brainstorm_validation")]
                }
            
            print(f"✅ Successfully brainstormed tool: {result.get('name')}")
            
            return {
                "status": WorkflowStatus.BRAINSTORMING,
                "messages": [self.helpers.create_message(
                    json.dumps(result, ensure_ascii=False, indent=2), "brainstorm")],
                "tool_name": result.get("name"),
                "tool_description": result.get("description"),
                "tool_input_schema": result.get("input_schema"),
                "tool_output_schema": result.get("output_schema"),
                "required_packages": result.get("required_packages", []),
                "validation_error": None
            }
            
        except Exception as e:
            error_msg = f"Brainstorm execution failed: {str(e)}"
            print(f"❌ {error_msg}")
            return self.helpers.handle_error(error_msg) | {
                "status": WorkflowStatus.FAILED,
                "messages": [self.helpers.create_message(error_msg, "brainstorm_exception")]
            }
    
    def research_node(self, state: AgentState) -> Dict:
        """Research information for tool creation."""
        print("🔬 Researching...")
        
        # Simplified research - could be enhanced with actual web search
        research_result = f"Research for {state.get('tool_name', 'tool')} capability"
        
        return {
            "messages": [self.helpers.create_message(research_result, "research")],
            "research_result": research_result
        }
    
    def generate_node(self, state: AgentState) -> Dict:
        """Generate tool code."""
        print("⚙️ Generating code...")
        
        requirements = [
            f"Function name: {state['tool_name']}",
            f"Description: {state['tool_description']}",
            f"Input: {json.dumps(state['tool_input_schema'])}",
            f"Output: {json.dumps(state['tool_output_schema'])}",
            f"Packages: {state.get('required_packages', [])}"
        ]
        
        # Add error feedback if retry
        if state.get("validation_error"):
            requirements.append(f"Fix this error: {state['validation_error']}")
        
        code = script_generate.invoke({
            "requirements": "\n".join(requirements),
            "references": state.get("research_result", "")
        }).strip()
        
        # Check if more research needed
        if "NEED_MORE_INFO" in code or code.startswith("Need more"):
            return {
                "status": WorkflowStatus.RESEARCHING,
                "need_more_research": True
            }
        
        self.helpers.save_artifact(state["run_id"], f"code/{state['tool_name']}.py", code)
        
        return {
            "status": WorkflowStatus.GENERATING,
            "generated_code": code,
            "validation_passed": False,
            "validation_error": None
        }
    
    def validate_node(self, state: AgentState) -> Dict:
        """Validate generated code."""
        print("🧪 Validating code...")
        
        result = code_execute_local.invoke({
            "code": state["generated_code"],
            "packages": state.get("required_packages", []),
            "tool_name": state["tool_name"],
            "use_isolated_env": True
        })
        
        success = not (isinstance(result, str) and result.startswith("[Error]"))
        
        self.helpers.save_artifact(state["run_id"], f"validation/{state['tool_name']}.txt", str(result))
        
        if not success:
            try:
                log_failure_pattern(state["tool_name"], result)
            except Exception:
                pass
        
        return {
            "validation_passed": success,
            "validation_error": None if success else result,
            "generation_retry_count": state.get("generation_retry_count", 0) + 1
        }
    
    def register_node(self, state: AgentState) -> Dict:
        """Register successful tool."""
        print("📝 Registering tool...")
        
        # Clean code
        code = state["generated_code"]
        code = re.sub(r'if __name__ == "__main__":.*', '', code, flags=re.DOTALL).strip()
        
        tool_payload = {
            "name": state["tool_name"],
            "description": state["tool_description"],
            "code": code,
            "input": state["tool_input_schema"],
            "output": state["tool_output_schema"],
            "packages": state.get("required_packages", [])
        }
        
        insert_mcp.invoke({"tool": tool_payload})
        
        success_msg = f"Tool '{state['tool_name']}' registered successfully"
        return {"messages": [self.helpers.create_message(success_msg, "register")]} 