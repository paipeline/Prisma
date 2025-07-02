import json
from pydantic import BaseModel
import re
from langchain_core.tools import tool
from typing import Union

class Tool(BaseModel):
    name: str
    description: str
    code: str
    input: dict
    output: dict = {}
    packages: list = []
    system_packages: list = []


def extract_function_code(code: str) -> str:
    """
    Extracts only the function definitions from Python code, removing any __main__ section.
    This ensures we store only reusable function code in the MCP registry.
    """
    # Split the code by lines
    lines = code.split('\n')
    
    # Find where the __main__ section starts
    main_start = -1
    for i, line in enumerate(lines):
        if line.strip().startswith('if __name__ == '):
            main_start = i
            break
    
    # If __main__ section found, return only the code before it
    if main_start != -1:
        function_lines = lines[:main_start]
        # Remove trailing empty lines
        while function_lines and not function_lines[-1].strip():
            function_lines.pop()
        return '\n'.join(function_lines)
    
    # If no __main__ section, return the original code
    return code

@tool
def insert_mcp(tool: Union[Tool, dict]):
    """
    Insert tool to the mcp_registry.json file.
    Accepts either a Tool object or a dictionary with tool information.
    """
    # Allow LangChain wrappers that send {"tool": {...}}
    if isinstance(tool, dict):
        if "tool" in tool and isinstance(tool["tool"], dict):
            tool = tool["tool"]
        # After potential unwrapping, convert to Tool
    if isinstance(tool, dict):
        tool = Tool(**tool)
    
    # Extract only the function code before storing, remove __main__ section
    tool.code = extract_function_code(tool.code)
    
    data = []
    try:
        with open("mcp_registry.json", "r") as f:
            data = json.load(f) 
    except FileNotFoundError:
        # If the file doesn't exist, we'll create it with the first tool.
        pass

    data.append(tool.model_dump())
    with open("mcp_registry.json", "w") as f:
        json.dump(data, f, indent=4)
    return f"Tool {tool.name} added to the mcp_registry.json file"


def get_mcp_registry(capability_query: str = None):
    """
    get the mcp_registry.json file, returning only tool metadata (name, desc, i/o)
    """
    try:
        with open("mcp_registry.json", "r") as f:
            registry = json.load(f)
    except FileNotFoundError:
        return [] # Return empty list if registry doesn't exist yet
    
    # Return only the metadata, not the full code
    metadata_registry = []
    for tool in registry:
        metadata_registry.append({
            "name": tool.get("name"),
            "description": tool.get("description"),
            "input": tool.get("input"),
            "output": tool.get("output"),
        })
    return metadata_registry

def get_mcp_by_name(name: str) -> dict | None:
    """
    Get the full tool definition for a specific tool by name.
    """
    try:
        with open("mcp_registry.json", "r") as f:
            registry = json.load(f)
    except FileNotFoundError:
        return None # Registry doesn't exist

    for tool in registry:
        if tool.get("name") == name:
            return tool
    return None

def get_mcp_code(name: str) -> str:
    """
    Gets the full Python code for an existing tool from the MCP registry by its name.
    Use this to retrieve the source code of a tool you want to modify or adapt for a new purpose.
    """
    try:
        with open("mcp_registry.json", "r") as f:
            registry = json.load(f)
    except FileNotFoundError:
        return "Tool not found." # Consistent with original behavior
        
    for tool in registry:
        if tool.get("name") == name:
            return tool.get("code")
    return "Tool not found."

def cleanup_mcp_registry():
    """
    Clean up the MCP registry by removing __main__ sections from all stored tools.
    This should be called once to fix any existing tools that have __main__ sections.
    """
    with open("mcp_registry.json", "r") as f:
        registry = json.load(f)
    
    updated = False
    for tool in registry:
        if 'code' in tool and tool['code']:
            original_code = tool['code']
            cleaned_code = extract_function_code(original_code)
            if cleaned_code != original_code:
                tool['code'] = cleaned_code
                updated = True
    
    if updated:
        with open("mcp_registry.json", "w") as f:
            json.dump(registry, f, indent=4)
        return "MCP registry cleaned up - removed __main__ sections from existing tools"
    else:
        return "MCP registry is already clean - no __main__ sections found"

# --- Failure logging helper (added for automatic logging) ---

def log_failure_pattern(tool_name: str, error_message: str, context: str = ""):
    """Append a simple failure record into mcp_failure_patterns.json"""
    import datetime, os, json
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "tool_name": tool_name,
        "error": error_message,
        "context": context,
    }
    path = "mcp_failure_patterns.json"
    data = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = []
    data.append(entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return "logged"