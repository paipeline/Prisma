"""
Refactored CodeReAct workflow implementation.
This is now a lightweight orchestrator that uses modular components.
"""

import json
import uuid
import warnings
from dotenv import load_dotenv

# Suppress warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

from src.types.state import create_default_agent_state
from src.core.graph.graph_builder import GraphBuilder
from src.utils.run_logger import RunLogger


class CodeReActWorkflow:
    """CodeReAct workflow orchestrator."""
    def __init__(self, interactive: bool = False):
        self.graph_builder = GraphBuilder(interactive=interactive)
        self.graph = self.graph_builder.build_graph()
    
    # --- Public Interface ---
    
    def run(self, query: str) -> str:
        """Run the workflow for a query."""
        load_dotenv()
        
        run_id = str(uuid.uuid4())
        run_logger = RunLogger(query)
        
        initial_state = create_default_agent_state(query, run_id)
        
        self.graph_builder.helpers.log_event(run_id, "workflow_started", {"query": query})
        
        print(f"🚀 Starting CodeReAct workflow: '{query}'")
        
        try:
            run_logger.log_prompt(f"Query: {query}")
            
            final_state = self.graph.invoke(initial_state, {
                "recursion_limit": 200
            })
            
            result = final_state.get("final_answer", "No result")
            print(f"🏁 Result: {result}")
            
            run_logger.log_final_answer(result)
            return result
            
        except Exception as e:
            error_msg = f"Workflow error: {e}"
            print(f"❌ {error_msg}")
            return error_msg
    
    def visualize(self, filename="workflow.png"):
        """Save workflow visualization."""
        try:
            img_data = self.graph.get_graph().draw_png()
            with open(filename, "wb") as f:
                f.write(img_data)
            print(f"Workflow diagram saved to {filename}")
        except Exception as e:
            print(f"Visualization error: {e}")

if __name__ == '__main__':
    workflow = CodeReActWorkflow()
    # test the workflow with preset questions
    questions_file = "src/questions/capability_questions.json"
    try:
        with open(questions_file, 'r') as f:
            questions = json.load(f)
        for i, item in enumerate(questions):
            question = item.get("question")
            if question:
                print(f"\n--- Test {i+1} ---")
                result = workflow.run(question) 
                print(f"Result: {result}")

    except Exception as e:
        print(f"Test error: {e}")

# Export the graph for LangGraph CLI
workflow = CodeReActWorkflow(interactive=True)
graph = workflow.graph