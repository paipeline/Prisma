from typing import Literal

# Define available LLM types
#llm openai
#reasoning groq/qwen3
#vision openai
LLMType = Literal["llm", "reasoning", "vision"]

# Define agent-LLM mapping
AGENT_LLM_MAP: dict[str, LLMType] = {
    # reAct
    "manager": "llm",
    "web": "llm",
    "script": "llm",

    # simple reAct
    "subtask": "llm",
    "mcp_brainstorming": "llm",
    "final_report": "llm",
}
