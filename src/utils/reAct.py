from langgraph.prebuilt import create_react_agent
from src.prompts.template import apply_prompt_template
from src.utils.llm_helper import get_llm_by_type

from src.config.llm_type import AGENT_LLM_MAP
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.base import BaseCheckpointSaver



# Create agents using configured LLM types
def create_agent(agent_name: str, agent_type: str, tools: list, prompt_template: str, checkpointer: BaseCheckpointSaver = None):
    """Factory function to create agents with consistent configuration."""
    return create_react_agent(
        name=agent_name,
        model=get_llm_by_type(AGENT_LLM_MAP[agent_type]),
        tools=tools,
        checkpointer=checkpointer,
        prompt=lambda state: apply_prompt_template(prompt_template, state),
    )




if __name__ == "__main__":
    agent = create_agent(
        agent_name="manager",
        agent_type="manager",
        tools=[],
        prompt_template="manager",
    )
    print(agent.invoke({"messages": [{"role": "user", "content": "what is the weather in sf"}]}))   