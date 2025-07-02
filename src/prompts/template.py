# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

import os
import dataclasses
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape
from src.types.state import AgentState
from src.config.configuration import Configuration

# Initialize Jinja2 environment for apply_prompt_template
env = Environment(
    loader=FileSystemLoader(os.path.dirname(__file__)),
    autoescape=select_autoescape(),
    trim_blocks=True,
    lstrip_blocks=True,
)

def get_prompt_template(prompt_name: str) -> str:
    """
    Load a prompt as plain text from a file.
    This function reads the file directly to avoid any templating issues with Jinja2.

    Args:
        prompt_name: Name of the prompt template file (without .md extension)

    Returns:
        The raw content of the prompt file as a string.
    """
    prompt_path = os.path.join(os.path.dirname(__file__), f"{prompt_name}.md")
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        raise ValueError(f"Prompt template file not found: {prompt_path}")
    except Exception as e:
        raise ValueError(f"Error loading prompt {prompt_name}: {e}")


def apply_prompt_template(
    prompt_name: str, state: AgentState, configurable: Configuration = None
) -> list:
    """
    Apply template variables to a prompt template and return formatted messages.

    Args:
        prompt_name: Name of the prompt template to use
        state: Current agent state containing variables to substitute

    Returns:
        List of messages with the system prompt as the first message
    """
    messages = state.get("messages", [])
    
    # Extract the user's original query from the start of the conversation
    original_query = ""
    if messages and messages[0].type == 'user':
        original_query = messages[0].content
    
    # Convert state to dict for template rendering, adding the original query
    state_vars = {
        "CURRENT_TIME": datetime.now().strftime("%a %b %d %Y %H:%M:%S %z"),
        "original_query": original_query,
        **state,
    }

    # Add configurable variables
    if configurable:
        state_vars.update(dataclasses.asdict(configurable))

    try:
        template = env.get_template(f"{prompt_name}.md")
        system_prompt = template.render(**state_vars)
        return [{"role": "system", "content": system_prompt}] + state["messages"]
    except Exception as e:
        raise ValueError(f"Error applying template {prompt_name}: {e}")