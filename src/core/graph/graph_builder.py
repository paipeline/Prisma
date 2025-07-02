"""
Graph builder for the CodeReAct workflow system.
Constructs the LangGraph workflow with nodes and edges.
"""

from langgraph.graph import StateGraph, END
from src.types import AgentState
from src.core.graph.decision_engine import DecisionEngine
from src.core.workflow_helpers import WorkflowHelpers
from src.core.nodes import PlanningNodes, CapabilityNodes, ExecutionNodes, CompletionNodes


class GraphBuilder:
    """Builds the CodeReAct workflow graph."""
    
    def __init__(self, interactive: bool = False):
        self.helpers = WorkflowHelpers(interactive=interactive)
        self.decision_engine = DecisionEngine()
        
        # Initialize node groups
        self.planning_nodes = PlanningNodes(self.helpers)
        self.capability_nodes = CapabilityNodes(self.helpers)
        self.execution_nodes = ExecutionNodes(self.helpers)
        self.completion_nodes = CompletionNodes(self.helpers)
    
    def build_graph(self) -> StateGraph:
        """Build the complete workflow graph."""
        workflow = StateGraph(AgentState)
        
        # Add all nodes
        self._add_nodes(workflow)
        
        # Set entry point
        workflow.set_entry_point("plan")
        
        # Add edges
        self._add_edges(workflow)
        
        return workflow.compile()
    
    def _add_nodes(self, workflow: StateGraph):
        """Add all workflow nodes."""
        nodes = {
            # Planning nodes
            "plan": self.planning_nodes.plan_node,
            "maybe_request_user_input": self.planning_nodes.maybe_request_user_input_node,
            "next_subtask": self.planning_nodes.next_subtask_node,
            
            # Capability nodes
            "resolve": self.capability_nodes.resolve_node,
            "brainstorm": self.capability_nodes.brainstorm_node,
            "research": self.capability_nodes.research_node,
            "generate": self.capability_nodes.generate_node,
            "validate": self.capability_nodes.validate_node,
            "register": self.capability_nodes.register_node,
            
            # Execution nodes
            "prepare_args": self.execution_nodes.prepare_args_node,
            "execute": self.execution_nodes.execute_node,
            
            # Completion nodes
            "finish": self.completion_nodes.finish_node,
            "review": self.completion_nodes.review_node,
            "fail": self.completion_nodes.fail_node,
        }
        
        for name, func in nodes.items():
            workflow.add_node(name, func)
    
    def _add_edges(self, workflow: StateGraph):
        """Add workflow edges."""
        # Linear paths
        workflow.add_edge("plan", "maybe_request_user_input")
        workflow.add_edge("maybe_request_user_input", "next_subtask")
        workflow.add_edge("next_subtask", "resolve")
        workflow.add_edge("research", "generate")
        workflow.add_edge("register", "finish")
        workflow.add_edge("execute", "finish")
        
        # Conditional failure edge
        workflow.add_conditional_edges(
            "fail",
            self.decision_engine.decide_failure,
            {
                "end": END,
                "retry": "next_subtask"
            }
        )
        
        # Conditional edges
        workflow.add_conditional_edges(
            "resolve",
            self.decision_engine.decide_resolution,
            {
                "cache": "finish",
                "existing": "prepare_args", 
                "create": "brainstorm"
            }
        )
        
        workflow.add_conditional_edges(
            "brainstorm",
            self.decision_engine.decide_brainstorm,
            {"continue": "research", "fail": "fail"}
        )
        
        workflow.add_conditional_edges(
            "generate",
            self.decision_engine.decide_generation,
            {
                "research": "research",
                "validate": "validate",
                "fail": "fail"
            }
        )
        
        workflow.add_conditional_edges(
            "validate",
            self.decision_engine.decide_validation,
            {
                "register": "register",
                "retry": "generate", 
                "fail": "fail"
            }
        )
        
        workflow.add_conditional_edges(
            "prepare_args",
            self.decision_engine.decide_prepare_args,
            {"execute": "execute", "fail": "fail"}
        )
        
        workflow.add_conditional_edges(
            "finish",
            self.decision_engine.decide_finish,
            {"next": "next_subtask", "review": "review", "end": END}
        )
        
        workflow.add_conditional_edges(
            "review",
            self.decision_engine.decide_review,
            {"end": END, "plan": "plan", "fail": "fail"}
        ) 