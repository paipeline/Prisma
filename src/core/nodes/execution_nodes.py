"""
Execution nodes for the CodeReAct workflow.
Handles tool argument preparation and execution.
"""

import json
import hashlib
import os
from typing import Dict

from src.types import AgentState
from src.core.workflow_helpers import WorkflowHelpers
from src.utils.cache_helper import get_cached_output
from src.core.tools import get_mcp_code, code_execute_local


class ExecutionNodes:
    """Nodes responsible for tool execution."""
    
    def __init__(self, helpers: WorkflowHelpers):
        self.helpers = helpers
    
    def prepare_args_node(self, state: AgentState) -> Dict:
        """Prepare tool arguments."""
        print("📝 Preparing arguments...")
        
        schema = state["tool_input_schema"]
        if not schema or not schema.get("properties"):
            return {"tool_arguments": {}}
        
        system_prompt = """Extract arguments from user query based on the JSON schema.
        Return a JSON object (dictionary) that matches the schema, not an array."""
        
        result, raw = self.helpers.llm_json_task(system_prompt, f"Query: {state['active_query']}\nSchema: {json.dumps(schema)}")
        
        if result is None:
            # If schema only has optional fields, it's acceptable to pass no arguments
            result = {}
        
        # Ensure result is a dictionary, not a list
        if isinstance(result, list):
            print(f"⚠️ LLM returned list instead of dict: {result}")
            # If it's a list with one dict element, use that
            if len(result) == 1 and isinstance(result[0], dict):
                result = result[0]
            else:
                # Fallback to empty dict
                result = {}
        elif not isinstance(result, dict):
            print(f"⚠️ LLM returned unexpected type {type(result)}: {result}")
            result = {}
        
        # 🔄 Merge with shared memory for missing keys
        shared_mem = state.get("memory", {}) or {}
        if schema and isinstance(schema.get("properties", None), dict):
            for key in schema["properties"].keys():
                if key not in result and key in shared_mem:
                    result[key] = shared_mem[key]
        
        return {"tool_arguments": result}
    
    def execute_node(self, state: AgentState) -> Dict:
        """Execute tool with arguments."""
        print("🚀 Executing tool...")
        
        tool_name = state["tool_name"]
        tool_args = state.get("tool_arguments", {})
        
        # Defensive check: ensure tool_args is a dictionary
        if not isinstance(tool_args, dict):
            print(f"⚠️ tool_arguments is not a dict (type: {type(tool_args)}): {tool_args}")
            tool_args = {}
        
        # Try cache first
        try:
            cached = get_cached_output.invoke({
                "tool_name": tool_name,
                "input_signature": tool_args
            })
            if not str(cached).startswith(("[CacheMiss]", "[Error]")):
                print("💾 Using cached result")
                results = state.get("subtask_results", []) + [str(cached)]
                return {
                    "messages": [self.helpers.create_message(str(cached), "execute")],
                    "subtask_results": results
                }
        except Exception:
            pass
        
        tool_code = get_mcp_code.invoke({"name": tool_name})
        arg_strs = [f'{k}="{v}"' if isinstance(v, str) else f'{k}={v}' 
                   for k, v in tool_args.items()]
        call_str = f'{tool_name}({", ".join(arg_strs)})'
        
        executable = f"""{tool_code}

if __name__ == '__main__':
    try:
        result = {call_str}
        print(result)
    except Exception as e:
        print(f'[Error] {{e}}')
"""
        
        result = code_execute_local.invoke({
            "code": executable,
            "packages": state.get("required_packages", []),
            "tool_name": tool_name,
            "use_isolated_env": True
        })
        
        # 🧠 Persist returned values to shared memory if possible
        updated_memory = state.get("memory", {}) or {}
        try:
            # Try to parse JSON object from result string
            parsed = None
            if isinstance(result, dict):
                parsed = result
            else:
                import json, re as _re
                # Check if result looks like JSON
                res_str = str(result).strip()
                if res_str.startswith("{") and res_str.endswith("}"):
                    parsed = json.loads(res_str)
                # Simple key=value on single line
                elif _re.match(r"^\w+\s*=\s*.+$", res_str):
                    k, v = res_str.split("=", 1)
                    parsed = {k.strip(): v.strip()}
            if parsed and isinstance(parsed, dict):
                updated_memory.update(parsed)
        except Exception:
            pass
        
        if not str(result).startswith(("[Error]", "[Workflow Error]")):
            self._cache_result(tool_name, tool_args, str(result))
        
        self.helpers.save_artifact(state["run_id"], f"execution/{tool_name}.txt", str(result))
        self.helpers.log_event(state["run_id"], "tool_executed", {
            "tool": tool_name, 
            "args": tool_args,
            "success": not str(result).startswith("[Error]")
        })
        
        results = state.get("subtask_results", []) + [str(result)]
        
        return {
            "messages": [self.helpers.create_message(str(result), "execute")],
            "subtask_results": results,
            "memory": updated_memory
        }
    
    def _cache_result(self, tool_name: str, args: dict, result: str):
        """Cache successful tool execution."""
        try:
            cache_dir = os.path.join(".prisma", "cache", tool_name)
            os.makedirs(cache_dir, exist_ok=True)
            
            sig_hash = hashlib.sha256(
                json.dumps(args, sort_keys=True).encode()
            ).hexdigest()[:16]
            
            cache_file = os.path.join(cache_dir, f"{sig_hash}.txt")
            with open(cache_file, "w") as f:
                f.write(result)
        except Exception:
            pass 