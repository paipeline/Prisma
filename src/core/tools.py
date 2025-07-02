# prisma Agent Workflow - Tools
# This file contains the tool definitions for the prisma Manager Agent.

import jinja2
import os
import json
import re
import numpy as np

from langchain_core.tools import tool
from src.utils.llm_helper import basic_llm
from src.utils.web_agent import run_web_agent
from src.utils.code_runner import code_execute_local
from src.utils.env_manager import get_env_manager
from src.utils.mcp_helper import insert_mcp, get_mcp_registry, get_mcp_code as mcp_helper_get_mcp_code

# === Jinja2 Environment Setup ===
prompt_dir = os.path.join(os.path.dirname(__file__), '..', 'prompts')
jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(prompt_dir),
    autoescape=jinja2.select_autoescape(['html', 'xml', 'md'])
)

def render_prompt(template_name: str, context: dict) -> str:
    """Renders a Jinja2 template with the given context."""
    template = jinja_env.get_template(f"{template_name}.md")
    return template.render(context)

# === Tool Definitions ===

@tool
def web_search_agent(query: str) -> dict:
    """
    A powerful agent that can search the web, browse pages, and search GitHub to answer a query. 
    Use this for any information gathering or research.
    Returns a dictionary with 'summary' and 'sources'.
    """
    return run_web_agent(query)

@tool
def query_mcp_registry(capability_query: str) -> list[dict]:
    """
    Searches the MCP registry for the best tool to match a capability query
    using LLM-driven semantic analysis.
    """
    print(f"--- TOOL: Searching MCP Registry for: '{capability_query}' ---")
    
    registry = get_mcp_registry()
    if not registry:
        print("Registry is empty. No tools to search.")
        return []

    # Prepare the context for the LLM
    tools_context = "\n".join([
        f"- {tool.get('name', 'Unnamed')}: {tool.get('description', 'No description')}"
        for tool in registry
    ])

    prompt = render_prompt("query_mcp_registry", {
        "capability_query": capability_query,
        "tools_list_string": tools_context
    })
    
    # Use a powerful LLM to make the decision
    llm = basic_llm
    response = llm.invoke(prompt)
    
    try:
        # Extract JSON from the response
        json_match = re.search(r"\{.*\}", response.content, re.DOTALL)
        if not json_match:
            print(f"LLM Reasoning did not produce valid JSON: {response.content}")
            return []
            
        decision = json.loads(json_match.group(0))
        
        print(f"LLM Reasoning: {decision.get('reasoning', 'N/A')}")

        if decision.get("match") is True and decision.get("tool_name"):
            tool_name = decision["tool_name"]
            print(f"LLM decided the best match is: '{tool_name}'")
            # Find and return the chosen tool
            for tool_data in registry:
                if tool_data.get("name") == tool_name:
                    return [tool_data] # Return as a list
            print(f"Warning: LLM chose '{tool_name}', but it was not found in the registry.")
            return []
        else:
            print("LLM decided no suitable tool exists.")
            return []
            
    except (json.JSONDecodeError, KeyError) as e:
        print(f"Error processing LLM decision: {e}\nRaw Response: {response.content}")
        return []

@tool
def mcp_brainstorm(task_description: str) -> str:
    """
    When you need a new tool, use this to brainstorm a plan for it.
    Takes a description of the required tool and returns a JSON plan.
    """
    context = {"task_description": task_description, "mcp_registry": str(get_mcp_registry())}
    prompt = render_prompt("mcp_brainstorming", context)
    response = basic_llm.invoke(prompt)
    return response.content

@tool
def script_generate(requirements: str, references: str) -> str:
    """
    When you have a plan for a new tool, use this to generate the code.
    Takes a string describing the requirements and a string of reference code.
    Returns the raw python script as a string.
    """
    context = {"requirements": requirements, "references": references}
    prompt = render_prompt("script", context)
    response = basic_llm.invoke(prompt)
    # Return the raw code, removing any potential think blocks or markdown
    content = response.content
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
    content = re.sub(r"```python\s*(.*?)\s*```", r"\1", content, flags=re.DOTALL).strip()
    # Final cleanup to remove any trailing backslashes that cause syntax errors
    if content.endswith('\\'):
        content = content[:-1]
    return content

@tool
def detect_finish(original_request: str, current_answer: str) -> dict:
    """
    Determines if the agent's latest answer fully addresses the user's original request.

    This function uses an LLM to evaluate if the current answer is a complete and
    satisfactory resolution to the initial query.

    Args:
        original_request: The user's first query in the conversation.
        current_answer: The agent's latest proposed answer.

    Returns:
        A dictionary with 'finish' (boolean) and 'reason' (string) keys.
    """
    prompt = f"""
    Original user request: {original_request}
    Proposed answer: {current_answer}

    Guidelines for your decision:
    • If the user asked for a video, image, or other artifact to be produced and the answer returns a JSON object containing keys such as `video_path`, `image_path`, or a `status: success`, this likely satisfies the request.
    • If the answer explicitly states an output file was saved (e.g., ends with `.mp4`, `.avi`, `.png`, `.jpg`), that counts as having shown or stored the result unless the user explicitly required further processing.
    • Do not require conversational niceties; focus only on whether the functional requirement is met.

    Is the proposed answer a complete and final resolution for the original request?
    Respond with a JSON object with two keys:
    1. "finish": a boolean value (true or false).
    2. "reason": a brief string explaining why the task is or is not finished.
    """
    
    response = basic_llm.invoke(prompt)
    response_content = response.content.strip()

    match = re.search(r"\{.*\}", response_content, re.DOTALL)
    if not match:
        return {"finish": False, "reason": f"LLM did not return valid JSON: {response_content}"}

    json_string = match.group(0)
    try:
        result = json.loads(json_string)
        if "finish" not in result or "reason" not in result or not isinstance(result.get("finish"), bool):
             return {"finish": False, "reason": f"LLM returned malformed JSON: {response_content}"}
        return result
    except json.JSONDecodeError:
        return {"finish": False, "reason": f"LLM did not return valid JSON: {response_content}"}

@tool
def finish(answer: str):
    """
    Use this tool to signify that you have completed the task.
    The `answer` parameter should be the final, complete response to the user.
    """
    return answer

@tool
def get_prisma_env_info():
    """
    Get information about the current execution environment.
    Returns details about the PrismaRunEnv environment capabilities.
    """
    env_manager = get_env_manager()
    return env_manager.get_env_info()

@tool
def cleanup_environment():
    """
    Note: PrismaRunEnv is persistent and will remain on your computer.
    This function provides information about the environment but does not delete it.
    """
    env_manager = get_env_manager()
    env_manager.cleanup()
    return "PrismaRunEnv information displayed. Environment remains persistent on your system."

@tool
def request_user_input(question: str) -> str:
    """

    Asks the user for input. Use this when you need information from the user,
    like an API key, a file path, or clarification.
    Returns the user's response as a string.
    """
    print(f"\nprisma needs your help: {question}")
    user_response = input("> ")
    return user_response

@tool
def get_mcp_code(name: str):
    """Retrieves the code for an existing MCP."""
    result = mcp_helper_get_mcp_code(name)
    print(f"DEBUG: get_mcp_code returned: {result}")
    return result

@tool
def get_run_log(run_id: str) -> dict:
    """Retrieve the raw event JSONL and a list of stored artifacts for a given run.

    Returns a dictionary with keys:
      events: Full JSONL content as a single string (or error message).
      artifacts: List of artifact paths relative to the run's artifact directory.
    """
    import os
    from src.utils.run_artifact import list_artifacts

    events_path = os.path.join("runs", run_id, "events.jsonl")
    try:
        with open(events_path, "r", encoding="utf-8") as fh:
            events_text = fh.read()
    except FileNotFoundError:
        events_text = f"[Error] events.jsonl not found for run_id={run_id}"

    try:
        artifacts = list_artifacts(run_id)
    except Exception as e:
        artifacts = [f"[Error] could not list artifacts: {e}"]

    return {"events": events_text, "artifacts": artifacts}

@tool
def save_artifact(run_id: str, relative_path: str, content: str) -> str:
    """Save arbitrary text content as a run artifact.

    Example:
        save_artifact(run_id="abc-123", relative_path="notes/analysis.md", content="Some text")
    """
    try:
        from src.utils.run_artifact import add_artifact
        abs_path = add_artifact(run_id, relative_path, content)
        return f"[Saved] {abs_path}"
    except Exception as e:
        return f"[Error] Could not save artifact: {e}" 