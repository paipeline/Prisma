"""
Workflow helper methods for the CodeReAct system.
Contains utility functions for logging, message creation, JSON parsing, etc.
"""

from typing import Optional, Dict, Any, Tuple
import json
import uuid
import re
from langchain_core.messages import ToolMessage, SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from src.utils.event_logger import log_event
from src.utils.llm_helper import get_llm_by_type


class WorkflowHelpers:
    """Helper methods for workflow operations."""
    
    def __init__(self, interactive: bool = False):
        self.llm = get_llm_by_type("llm")
        self._interactive = interactive
    
    @property
    def is_interactive(self) -> bool:
        """Check if the workflow is in interactive mode."""
        return self._interactive
    
    def log_event(self, run_id: str, event_type: str, data: Any = None):
        """Safe event logging."""
        try:
            log_event(run_id, event_type, data)
        except Exception:
            pass
    
    def save_artifact(self, run_id: str, path: str, content: str):
        """Safe artifact saving."""
        try:
            from src.utils.run_artifact import add_artifact
            add_artifact(run_id, path, content)
        except Exception:
            pass
    
    def create_message(self, content: str, tool_name: str) -> ToolMessage:
        """Create consistent tool messages."""
        return ToolMessage(
            content=content,
            name=tool_name,
            tool_call_id=str(uuid.uuid4())
        )
    
    def extract_json(self, text: str) -> Optional[dict | list]:
        """Extract JSON from LLM response."""
        if text is None:
            return None

        # Try markdown JSON block first (both object and array)
        match = re.search(r"```json\s*(\[.*?\]|\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        
        # Clean the text of any extra whitespace and newlines for better parsing
        text = text.strip()
        
        # Try finding JSON object FIRST (prioritize objects over arrays)
        try:
            start = text.find('{')
            if start != -1:
                brace_count = 0
                for i, char in enumerate(text[start:], start):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            # Found complete JSON object, try to parse it
                            json_str = text[start:i+1]
                            try:
                                return json.loads(json_str)
                            except json.JSONDecodeError:
                                # If parsing fails, continue looking for other JSON
                                pass
        except Exception:
            pass
        
        # Only try finding JSON array if no valid object was found
        try:
            start = text.find('[')
            if start != -1:
                bracket_count = 0
                for i, char in enumerate(text[start:], start):
                    if char == '[':
                        bracket_count += 1
                    elif char == ']':
                        bracket_count -= 1
                        if bracket_count == 0:
                            json_str = text[start:i+1]
                            try:
                                return json.loads(json_str)
                            except json.JSONDecodeError:
                                pass
        except Exception:
            pass
        
        return None
    
    def llm_json_task(self, system_prompt: str, user_input: str) -> Tuple[Optional[dict | list], str]:
        """Execute LLM task expecting JSON output."""
        # The prompts are pre-formatted, so we pass them as direct messages
        # to bypass the template engine and avoid variable parsing issues.
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_input)
        ]
        
        chain = self.llm | StrOutputParser()
        raw_result = chain.invoke(messages)
        #eliminate any <think>...</think> blocks
        raw_result = re.sub(r"<think>[\s\S]*?</think>", "", raw_result, flags=re.IGNORECASE)
        # Ensure raw_result is always a string to prevent TypeErrors
        if not isinstance(raw_result, str):
            raw_result = ""
        
        result = self.extract_json(raw_result)
        
        return result, raw_result
    
    def handle_error(self, error_msg: str, retry_count: int = None) -> dict:
        """Standard error handling."""
        updates = {"validation_error": error_msg}
        if retry_count is not None:
            updates["generation_retry_count"] = retry_count
        return updates 