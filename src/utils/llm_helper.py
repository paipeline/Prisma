# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

from pathlib import Path
from typing import Any, Dict
import os
import logging
from langchain_core.prompts import ChatPromptTemplate
from litellm import completion
from src.config.llm_type import LLMType

# Configure logging to suppress verbose litellm output
logging.getLogger("LiteLLM").setLevel(logging.WARNING)

from langchain_litellm import ChatLiteLLM
from typing import get_args

from src.config.loader import load_yaml_config

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Cache for LLM instances
_llm_cache: dict[LLMType, Any] = {}


def _get_config_file_path() -> str:
    """Get the path to the configuration file."""
    return str((Path(__file__).parent.parent.parent / "conf.yaml").resolve())


def _get_llm_type_config_keys() -> dict[str, str]:
    """Get mapping of LLM types to their configuration keys."""
    return {
        "llm": "LLM_MODEL",
        "reasoning": "REASONING_MODEL",
        "vision": "VISION_MODEL",
    }


def _get_env_llm_conf(llm_type: str) -> Dict[str, Any]:
    """
    Get LLM configuration from environment variables.
    Environment variables should follow the format: {LLM_TYPE}_MODEL__{KEY}
    e.g., LLM_MODEL__model, LLM_MODEL__api_key
    """
    prefix = f"{llm_type.upper()}_MODEL__"
    conf = {}
    
    # Read environment variables with the specified prefix
    for key, value in os.environ.items():
        if key.startswith(prefix):
            conf_key = key[len(prefix) :].lower()
            conf[conf_key] = value
    
    if "api_key" not in conf:
        if llm_type == "reasoning":
            # Reasoning models use GROQ API
            if "GROQ_API_KEY" in os.environ:
                conf["api_key"] = os.environ["GROQ_API_KEY"]
        else:
            # Other models use OpenAI API
            if "OPENAI_API_KEY" in os.environ:
                conf["api_key"] = os.environ["OPENAI_API_KEY"]
    
    return conf


def _create_llm_use_conf(
    llm_type: LLMType, conf: Dict[str, Any]
) -> Any:
    """Create LLM instance using configuration."""
    llm_type_config_keys = _get_llm_type_config_keys()
    config_key = llm_type_config_keys.get(llm_type)

    if not config_key:
        raise ValueError(f"Unknown LLM type: {llm_type}")

    llm_conf = conf.get(config_key, {})
    if not isinstance(llm_conf, dict):
        raise ValueError(f"Invalid LLM configuration for {llm_type}: {llm_conf}")

    # Get configuration from environment variables
    env_conf = _get_env_llm_conf(llm_type)

    # Merge configurations, with environment variables taking precedence
    merged_conf = {**llm_conf, **env_conf}

    if not merged_conf:
        raise ValueError(f"No configuration found for LLM type: {llm_type}")

    # Handle different LLM types
    if llm_type == "reasoning":
        # For reasoning models using Groq, remove api_base to avoid warnings
        merged_conf.pop("api_base", None)
        merged_conf.pop("base_url", None)
        return ChatLiteLLM(**merged_conf)
    else:
        # For OpenAI models (llm and vision types)
        return ChatLiteLLM(**merged_conf)


def get_llm_by_type(
    llm_type: LLMType,
) -> Any:
    """
    Get LLM instance by type. Returns cached instance if available.
    """
    if llm_type in _llm_cache:
        return _llm_cache[llm_type]

    conf = load_yaml_config(_get_config_file_path())
    llm = _create_llm_use_conf(llm_type, conf)
    _llm_cache[llm_type] = llm
    return llm


def get_configured_llm_models() -> dict[str, list[str]]:
    """
    Get all configured LLM models grouped by type.

    Returns:
        Dictionary mapping LLM type to list of configured model names.
    """
    try:
        conf = load_yaml_config(_get_config_file_path())
        llm_type_config_keys = _get_llm_type_config_keys()

        configured_models: dict[str, list[str]] = {}

        for llm_type in get_args(LLMType):
            # Get configuration from YAML file
            config_key = llm_type_config_keys.get(llm_type, "")
            yaml_conf = conf.get(config_key, {}) if config_key else {}

            # Get configuration from environment variables
            env_conf = _get_env_llm_conf(llm_type)

            # Merge configurations, with environment variables taking precedence
            merged_conf = {**yaml_conf, **env_conf}

            # Check if model is configured
            model_name = merged_conf.get("model")
            if model_name:
                configured_models.setdefault(llm_type, []).append(model_name)

        return configured_models

    except Exception as e:
        # Log error and return empty dict to avoid breaking the application
        print(f"Warning: Failed to load LLM configuration: {e}")
        return {}



basic_llm = get_llm_by_type("llm")      
reasoning_llm = get_llm_by_type("reasoning") 
vision_llm = get_llm_by_type("vision")


if __name__ == "__main__":
    print(basic_llm.model_name)
    print(reasoning_llm.model_name)
    print(vision_llm.model_name)

def get_prompt_template(template_name: str, prompts_dir: str = "src/prompts") -> ChatPromptTemplate:
    """
    Loads a prompt template from a .md file in the specified directory.
    """
    template_path = os.path.join(prompts_dir, template_name)

    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Prompt template not found at {template_path}")

    with open(template_path, "r", encoding="utf-8") as f:
        template_string = f.read()

    return ChatPromptTemplate.from_template(template_string)