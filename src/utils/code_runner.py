from dotenv import load_dotenv
import os
from typing import List
import subprocess
import tempfile
import shutil
import sys
import platform
import json
from langchain_core.tools import tool

load_dotenv()

# Import LocalRunnerResponse and environment managers
from src.utils.env_manager import (
    LocalRunnerResponse,
    get_env_manager, 
    get_persistent_env_manager, 
    PersistentEnvironmentManager
)

@tool
def code_execute_local(
    code: str, 
    packages: list = None, 
    system_packages: list = None, 
    function_name: str = None, 
    function_args: dict = None,
    tool_name: str | None = None,
    use_isolated_env: bool = False
) -> str:
    """
    Execute python code in the persistent PrismaRunEnv environment.
    This can either run the entire script or call a specific function within it.

    Args:
        code: The Python code to execute.
        packages: A list of Python packages to install via pip (optional).
        system_packages: A list of system-level packages to install (optional).
        function_name: The specific function to call within the code (optional).
                       If not provided, the script's __main__ block will be executed.
        function_args: A dictionary of arguments to pass to the specified function (optional).
        tool_name / use_isolated_env: Provide both to run inside a dedicated venv.

    Returns:
        A string containing the execution output, return value, or an error message.
    """
    if not shutil.which("conda"):
        return "[Error] Conda is not installed. Cannot run in PrismaRunEnv."

    if packages is None: packages = []
    if system_packages is None: system_packages = []
    if function_args is None: function_args = {}

    # Get the global PrismaRunEnv manager
    env_manager = get_env_manager()
    
    # Execute code in PrismaRunEnv, potentially calling a specific function
    result = env_manager.execute_code(
        code, 
        packages, 
        system_packages,
        function_name,
        function_args,
        tool_name=tool_name,
        use_isolated_env=use_isolated_env,
    )
    
    # Return the output if successful, otherwise return the error
    if result.error:
        return f"[Error] {result.error}"
    else:
        # If a function was called and returned a value, prioritize showing that
        if result.return_value is not None:
            return f"[Return Value]: {result.return_value}"
        # Otherwise, show the standard output
        return result.output or "[No output]"


def code_execute_local_raw(
    code: str, 
    packages: List[str] = None, 
    system_packages: List[str] = None,
    function_name: str = None,
    function_args: dict = None,
    tool_name: str | None = None,
    use_isolated_env: bool = False
) -> LocalRunnerResponse:
    """
    Execute python code in the persistent PrismaRunEnv environment (raw version returning LocalRunnerResponse).
    Args:
        code: Python code to execute.
        packages: List of python packages to install via pip.
        system_packages: List of system packages to install via pip.
    """
    if not shutil.which("conda"):
        return LocalRunnerResponse(error="Conda is not installed. Cannot run in PrismaRunEnv.")

    if packages is None: packages = []
    if system_packages is None: system_packages = []
    if function_args is None: function_args = {}

    # Get the global PrismaRunEnv manager
    env_manager = get_env_manager()
    
    # Execute code in PrismaRunEnv
    return env_manager.execute_code(
        code, 
        packages, 
        system_packages,
        function_name,
        function_args,
        tool_name=tool_name,
        use_isolated_env=use_isolated_env
    )

@tool
def get_prisma_env_info() -> str:
    """
    Get information about the current PrismaRunEnv environment.
    Shows installed packages and environment details.
    """
    env_manager = get_env_manager()
    info = env_manager.get_environment_info()
    
    if "error" in info:
        return f"[Error] {info['error']}"
    
    return f"""PrismaRunEnv Information:
- Name: {info['name']}
- Location: {info['path']}
- Python: {info['python_executable']}
- Installed packages: {info['installed_packages_count']}
- Sample packages: {', '.join(info['sample_packages'])}
"""

if __name__ == "__main__":
    print("=== Testing PrismaRunEnv ===")
    
    # Test the PrismaRunEnv environment
    env_manager = PersistentEnvironmentManager()
    
    try:
        print("\n1. Testing basic execution...")
        result1 = env_manager.execute_code('print("Hello from PrismaRunEnv!")', [])
        print(f"   Output: {result1.output.strip() if result1.output else result1.error}")
        
        print("\n2. Testing package installation...")
        result2 = env_manager.execute_code(
            'import requests; print(f"Requests version: {requests.__version__}")', 
            ['requests']
        )
        print(f"   Output: {result2.output.strip() if result2.output else result2.error}")
        
        print("\n3. Testing package reuse...")
        result3 = env_manager.execute_code(
            'import requests; print("Requests still available!")', 
            []  # No packages needed - already installed
        )
        print(f"   Output: {result3.output.strip() if result3.output else result3.error}")
        
        print("\n4. Environment info...")
        info = env_manager.get_environment_info()
        print(f"   Packages installed: {info.get('installed_packages_count', 0)}")
        
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n✅ PrismaRunEnv testing completed!")

