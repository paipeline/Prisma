"""
State type definitions for the CodeReAct workflow system.
"""

from typing import TypedDict, Annotated, Sequence, Optional, Dict, Any, List, Literal
import operator
from enum import Enum
from langchain_core.messages import BaseMessage, HumanMessage

# --- Workflow Status ---
class WorkflowStatus(Enum):
    """Workflow execution status."""
    PLANNING = "planning"
    RESOLVING = "resolving"
    BRAINSTORMING = "brainstorming"
    RESEARCHING = "researching"
    GENERATING = "generating"
    VALIDATING = "validating"
    REGISTERING = "registering"
    EXECUTING = "executing"
    FINISHING = "finishing"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"

# --- Validation Result ---
class ValidationResult(TypedDict):
    """Result of code validation."""
    passed: bool
    error_message: Optional[str]
    execution_output: Optional[str]
    retry_count: int

# --- Tool Metadata ---
class ToolMetadata(TypedDict):
    """Metadata for a tool."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    required_packages: List[str]
    code: Optional[str]
    arguments: Optional[Dict[str, Any]]

# --- Subtask Management ---
class SubtaskInfo(TypedDict):
    """Information about a subtask."""
    id: int
    description: str
    capability_query: str
    depends_on: List[int]
    status: Optional[WorkflowStatus]
    result: Optional[str]

# --- State Definition ---  
class AgentState(TypedDict):
    """
    Comprehensive state for the CodeReAct workflow.
    
    This state tracks all aspects of the workflow execution including:
    - Basic workflow info (messages, query, run_id)
    - Subtask management (current task, results, progress)
    - Tool information (metadata, code, arguments)
    - Workflow control (validation, errors, retry counts)
    - Execution results and review status
    """
    
    # --- Core Workflow Information ---
    messages: Annotated[Sequence[BaseMessage], operator.add]
    original_query: str
    run_id: str
    status: Optional[WorkflowStatus]
    
    # --- Subtask Management ---
    subtasks: Optional[List[SubtaskInfo]]
    current_subtask_idx: int
    active_query: str
    subtask_results: Optional[List[str]]
    has_more_subtasks: bool
    current_subtask_failure_count: int
    
    # --- Tool Metadata ---
    tool_name: Optional[str]
    tool_description: Optional[str]
    tool_code: Optional[str]
    tool_input_schema: Optional[Dict[str, Any]]
    tool_output_schema: Optional[Dict[str, Any]]
    required_packages: Optional[List[str]]
    tool_arguments: Optional[Dict[str, Any]]
    
    # --- Workflow Control ---
    validation_passed: bool
    validation_error: Optional[str]
    validation_result: Optional[ValidationResult]
    generation_retry_count: int
    environment_corrupted: bool
    need_more_research: bool
    
    # --- Execution & Results ---
    generated_code: Optional[str]
    research_result: Optional[str]
    cached_result: Optional[str]
    final_answer: Optional[str]
    
    # --- Quality Control ---
    review_passed: bool
    review_reason: Optional[str]
    review_retry_count: int
    
    # --- Resolution Strategy ---
    resolve_action: Optional[Literal["use_cache", "use_mcp", "create_new"]]
    
    # --- Error Handling ---
    last_error: Optional[str]
    error_context: Optional[str]

    # --- Shared Memory ---
    memory: Optional[Dict[str, Any]]

def create_default_agent_state(query: str, run_id: str) -> AgentState:
    """
    Create a default AgentState with all required fields properly initialized.
    
    Args:
        query: The user query to process
        run_id: Unique identifier for this workflow run
        
    Returns:
        AgentState with all fields set to appropriate defaults
    """
    return {
        # Core Workflow Information
        "messages": [HumanMessage(content=query)],
        "original_query": query,
        "run_id": run_id,
        "status": None,
        
        # Subtask Management
        "subtasks": None,
        "current_subtask_idx": 0,
        "active_query": query,
        "subtask_results": None,
        "has_more_subtasks": False,
        "current_subtask_failure_count": 0,
        
        # Tool Metadata
        "tool_name": None,
        "tool_description": None,
        "tool_code": None,
        "tool_input_schema": None,
        "tool_output_schema": None,
        "required_packages": None,
        "tool_arguments": None,
        
        # Workflow Control
        "validation_passed": False,
        "validation_error": None,
        "validation_result": None,
        "generation_retry_count": 0,
        "environment_corrupted": False,
        "need_more_research": False,
        
        # Execution & Results
        "generated_code": None,
        "research_result": None,
        "cached_result": None,
        "final_answer": None,
        
        # Quality Control
        "review_passed": False,
        "review_reason": None,
        "review_retry_count": 0,
        
        # Resolution Strategy
        "resolve_action": None,
        
        # Error Handling
        "last_error": None,
        "error_context": None,

        # Shared Memory
        "memory": {},
    } 