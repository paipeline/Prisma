from typing import List, Dict, Optional
import os
import shutil
import subprocess
import tempfile
import sys
import hashlib
import json
from pydantic import BaseModel
import platform
import re
from dotenv import dotenv_values
import codecs
import jinja2
import uuid

from src.utils.llm_helper import basic_llm
MAX_RETRIES = 5
class LocalRunnerResponse(BaseModel):
    output: str | None = None
    error: str | None = None
    packages: list[str] = []
    execution_results: list[str] = []
    return_value: str | None = None


class PersistentEnvironmentManager:
    """
    Manages a single persistent conda environment called 'PrismaRunEnv'.
    This environment stays on the user's computer and accumulates packages over time.
    All tools share this same environment to avoid duplication and conflicts.
    """
    
    def __init__(self, base_dir: str = None):
        """Initializes the persistent environment manager."""
        self.env_name = "PrismaRunEnv"
        self.base_dir = base_dir or os.getcwd()
        self.env_path = os.path.join(self.base_dir, ".prisma", self.env_name)
        self.workspace_path = os.path.join(self.base_dir, ".prisma", "workspace")
        self.python_executable = self._get_python_executable()
        self.installed_packages = set()
        self._initialized = False
        self.temp_script_path = None
        
    def _get_python_executable(self) -> str:
        """Gets the path to the python executable in the environment."""
        if platform.system() == "Windows":
            return os.path.join(self.env_path, "python.exe")
        return os.path.join(self.env_path, "bin", "python")

    def _extract_code_from_llm_output(self, input_str: str, original_packages: list, original_system_packages: list) -> (str, list, list):
        """
        Extracts executable code and package info from a raw LLM output string.
        Handles <think> blocks, and ```json``` or ```python``` markdown blocks.
        """
        # 1. Remove <think> blocks
        cleaned_str = re.sub(r'<think>.*?</think>', '', input_str, flags=re.DOTALL).strip()

        # 2. Try to parse JSON from a markdown block
        json_match = re.search(r"```json\s*({.*?})\s*```", cleaned_str, re.DOTALL)

        if json_match:
            try:
                data = json.loads(json_match.group(1))
                code = data.get("code", "")
                packages = data.get("packages", original_packages)
                system_packages = data.get("system_packages", original_system_packages)
                return code, packages, system_packages
            except json.JSONDecodeError:
                pass

        # 3. Try to extract python code from a markdown block
        python_match = re.search(r"```python\s*(.*?)\s*```", cleaned_str, re.DOTALL)
        if python_match:
            cleaned_str = python_match.group(1)

        # 4. Scan for inline package hints such as '# packages: numpy,pandas' or '# requirements: requests'
        pkg_pattern = re.compile(r"#\s*(?:packages|requirements)\s*:\s*([A-Za-z0-9_\-., ]+)")
        pkg_lines = pkg_pattern.findall(cleaned_str)
        inferred_packages = []
        if pkg_lines:
            for line in pkg_lines:
                parts = re.split(r"[ ,]+", line.strip())
                inferred_packages.extend([p for p in parts if p])

        combined_packages = list(dict.fromkeys((original_packages or []) + inferred_packages))  # dedup while preserving order

        return cleaned_str, combined_packages, original_system_packages


    def _environment_exists(self) -> bool:
        """Check if PrismaRunEnv already exists at its dedicated path."""
        return os.path.exists(self.env_path) and os.path.exists(self.python_executable)

    def _create_environment(self) -> bool:
        """Create a new conda environment."""
        if not shutil.which("conda"):
            print("[Error] Conda is not installed. Cannot create PrismaRunEnv.")
            return False
        try:
            python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
            
            # Ensure the parent directory exists
            os.makedirs(os.path.dirname(self.env_path), exist_ok=True)
            
            # Create conda environment
            create_command = ["conda", "create", "--prefix", self.env_path, "-y", f"python={python_version}"]
            
            print(f"--- Creating persistent environment 'PrismaRunEnv' at {self.env_path} ---")
            create_process = subprocess.run(create_command, capture_output=True, text=True)
            
            if create_process.returncode != 0:
                # Conda might fail if the dir is present but empty.
                if "already exists" in create_process.stderr:
                    print(f"--- Environment at {self.env_path} already exists. Skipping creation. ---")
                    return True
                print(f"Environment creation failed: {create_process.stderr}")
                return False
            
            print(f"✅ Environment 'PrismaRunEnv' created successfully.")
            return True
            
        except Exception as e:
            print(f"Environment creation error: {e}")
            return False

    def _get_installed_packages(self) -> set:
        """Get the set of installed packages in the environment."""
        if not self._initialized:
            return set()
            
        try:
            list_command = [self.python_executable, "-m", "pip", "list", "--format=json"]
            result = subprocess.run(list_command, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Warning: Could not list packages: {result.stderr}")
                return self.installed_packages # Return last known set
            
            installed = {pkg['name'] for pkg in json.loads(result.stdout)}
            self.installed_packages.update(installed)
            return self.installed_packages

        except (json.JSONDecodeError, FileNotFoundError):
            return self.installed_packages

    def ensure_environment(self) -> bool:
        """Ensures the persistent environment exists, creating it if necessary."""
        if self._initialized:
            return True
            
        if not self._environment_exists():
            if not self._create_environment():
                return False
        
        os.makedirs(self.workspace_path, exist_ok=True)
        
        self.python_executable = self._get_python_executable()
        self._initialized = True
        self.installed_packages = self._get_installed_packages()
        return True

    def install_packages(self, packages: List[str], system_packages: List[str]) -> (bool, Optional[str]):
        """
        Installs packages using a hybrid conda and pip strategy with a robust
        wipe-and-retry mechanism.
        Returns a tuple of (success: bool, error_message: Optional[str]).
        """
        for attempt in range(2): # Allow one full wipe and retry
            print(f"🔧 Ensuring environment is ready (Attempt {attempt + 1}/2)...")
            if not self.ensure_environment():
                print("❌ Failed to ensure environment is ready.")
                if attempt == 0:
                    self._wipe_environment()
                    continue
                return False, "Failed to ensure environment is ready."

            all_packages = (packages or []) + (system_packages or [])
            if not all_packages:
                print("✅ No new packages to install.")
                return True, None

            currently_installed = self._get_installed_packages()
            needed_packages = [p for p in all_packages if p.lower() not in currently_installed]

            if not needed_packages:
                print(f"✅ All required packages already installed: {all_packages}")
                return True, None

            print(f"📦 Needed packages for this run: {needed_packages}")
            
            # --- Hybrid Conda + Pip Strategy ---
            conda_packages = needed_packages.copy()
            pip_packages = []

            # 1. Attempt to install all with Conda first
            is_conda_env = os.path.exists(os.path.join(self.env_path, "conda-meta"))
            conda_error = None
            if is_conda_env:
                print(f"--- Conda attempting to install: {conda_packages} ---")
                conda_install_command = [
                    "conda", "install", "--prefix", self.env_path,
                    "-c", "conda-forge", "-y", "--no-update-deps"
                ] + conda_packages
                conda_process = subprocess.run(conda_install_command, capture_output=True, text=True)
                if conda_process.returncode != 0:
                    conda_error = conda_process.stderr
                    print(f"--- Conda command finished with errors. Pip will attempt to install remaining packages. Conda stderr:\n{conda_error}")

            # 2. Verify what was actually installed by Conda and determine what's left for Pip
            currently_installed = self._get_installed_packages()
            pip_packages = [p for p in needed_packages if p.lower() not in currently_installed]

            # 3. If there are packages left, install them with Pip
            if pip_packages:
                print(f"🐍 Pip will handle remaining packages: {pip_packages}")
                pip_install_command = [
                    self.python_executable, "-m", "pip", "install"
                ] + pip_packages
                pip_process = subprocess.run(pip_install_command, capture_output=True, text=True)

                if pip_process.returncode != 0:
                    pip_error = f"Pip installation failed:\n{pip_process.stderr}"
                    full_error = f"Conda Error:\n{conda_error}\n\nPip Error:\n{pip_error}" if conda_error else pip_error
                    print(f"❌ {full_error}")
                    
                    if attempt == 0:
                        print("🔥 Wiping environment due to installation failure and retrying...")
                        self._wipe_environment()
                        continue
                    else:
                        final_error = "Package installation failed after retry. Cannot proceed."
                        print(f"❌ {final_error}")
                        return False, f"{final_error}\n{full_error}"
            else:
                print("✅ Conda installed all required packages.")

            # If we reach here, all installations were successful or handled.
            print("✅ Hybrid package installation successful.")
            self._get_installed_packages() # Refresh installed list
            return True, None

        return False, "Exhausted package installation retries."

    def _wipe_environment(self):
        """Deletes the entire conda environment directory."""
        print(f"🗑️ Wiping environment at {self.env_path}...")
        self._initialized = False
        self.installed_packages.clear()
        if os.path.exists(self.env_path):
            try:
                shutil.rmtree(self.env_path)
                print("✅ Environment wiped successfully.")
            except OSError as e:
                print(f"❌ Error wiping environment: {e}. Manual deletion may be required.")

    # -------------------------------------------------------------
    # PUBLIC API --------------------------------------------------
    # -------------------------------------------------------------

    def execute_code(
        self,
        code: str,
        packages: List[str] = None,
        system_packages: List[str] = None,
        function_name: str = None,
        function_args: dict = None,
        *,
        tool_name: str | None = None,
        use_isolated_env: bool = False,
    ) -> LocalRunnerResponse:
        """Execute code in the persistent PrismaRunEnv environment."""
        if packages is None: packages = []
        if system_packages is None: system_packages = []
        if function_args is None: function_args = {}

        # ------------------------------------------------------------------
        # 0. If user requested isolated venv, switch context
        # ------------------------------------------------------------------
        original_env_path = self.env_path
        original_python_exec = self.python_executable

        if use_isolated_env and tool_name:
            iso_path = os.path.join(self.base_dir, ".prisma", "envs", tool_name.replace("/", "_"))
            self.env_path = iso_path
            # ensure venv exists
            if not os.path.exists(iso_path):
                os.makedirs(iso_path, exist_ok=True)
                subprocess.run([sys.executable, "-m", "venv", iso_path], check=True)
            # update python executable
            self.python_executable = self._get_python_executable()
            # Reset initialization state so package checks run against the new env
            self._initialized = False
            self.installed_packages.clear()

        executable_code, packages, system_packages = self._extract_code_from_llm_output(code, packages, system_packages)

        if not executable_code:
            return LocalRunnerResponse(error="No executable code found in the input.")
        
        # Unified error correction loop for both package and syntax errors
        max_retries = MAX_RETRIES
        current_packages = packages.copy()
        current_system_packages = system_packages.copy()
        current_code = executable_code
        
        # Accumulative fault log to track all failures across attempts
        fault_log = []
        
        # Track package-specific failures for intelligent discarding
        package_failure_counts = {}
        discarded_packages = {"packages": [], "system_packages": []}
        max_package_failures = 2  # Discard after 2 consecutive failures
        
        for attempt in range(max_retries):
            print(f"🔧 Attempt {attempt + 1}/{max_retries}: Preparing environment and code...")
            print(f"📦 Packages to install/verify: {current_packages if current_packages else 'None'}")
            print(f"🖥️  System packages required: {current_system_packages if current_system_packages else 'None'}")
            
            # Try to install packages
            package_success, package_error = self.install_packages(current_packages, current_system_packages)
            
            # Try to compile code for syntax validation
            syntax_error = None
            try:
                # Directly compile the code without unsafe unicode decoding
                compile(current_code, '<string>', 'exec')
                syntax_success = True
            except SyntaxError as e:
                syntax_error = e
                syntax_success = False
            
            # Record current attempt's failures in fault log and track package failures
            current_attempt_errors = []
            if not package_success:
                # Track individual package failures for intelligent discarding
                all_current_packages = current_packages + current_system_packages
                for pkg in all_current_packages:
                    package_failure_counts[pkg] = package_failure_counts.get(pkg, 0) + 1
                
                package_error_msg = f"[Attempt {attempt + 1}] Package installation failed. Error: {package_error}"
                current_attempt_errors.append(package_error_msg)
                fault_log.append(package_error_msg)
                
                # Check if we should discard persistently failing packages
                packages_to_discard = []
                system_packages_to_discard = []
                
                for pkg in current_packages:
                    if package_failure_counts.get(pkg, 0) >= max_package_failures:
                        packages_to_discard.append(pkg)
                
                for pkg in current_system_packages:
                    if package_failure_counts.get(pkg, 0) >= max_package_failures:
                        system_packages_to_discard.append(pkg)
                
                # Discard packages that have failed too many times
                if packages_to_discard or system_packages_to_discard:
                    for pkg in packages_to_discard:
                        if pkg in current_packages:
                            current_packages.remove(pkg)
                            discarded_packages["packages"].append(pkg)
                    
                    for pkg in system_packages_to_discard:
                        if pkg in current_system_packages:
                            current_system_packages.remove(pkg)
                            discarded_packages["system_packages"].append(pkg)
                    
                    discard_msg = f"[Attempt {attempt + 1}] Discarded persistently failing packages - Regular: {packages_to_discard}, System: {system_packages_to_discard}"
                    fault_log.append(discard_msg)
                    print(f"🗑️  {discard_msg}")
            
            if not syntax_success:
                syntax_error_msg = f"[Attempt {attempt + 1}] Syntax error: {syntax_error}"
                current_attempt_errors.append(syntax_error_msg)
                fault_log.append(syntax_error_msg)
            
            # If both package installation and syntax validation succeed, proceed with execution
            if package_success and syntax_success:
                print(f"🚀 Environment ready - executing code...")
                if fault_log:
                    print(f"📋 Previous issues resolved after {len(fault_log)} recorded failures")
                
                # If a function name is provided, create a loader script
                if function_name:
                    try:
                        # Save the user's code to a temporary file
                        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py', dir=self.workspace_path) as f:
                            f.write(current_code)
                            self.temp_script_path = f.name
                        
                        # The module name is the filename without the .py extension
                        module_name = os.path.basename(self.temp_script_path).replace('.py', '')

                        # Create the loader script
                        loader_code = f"""
import importlib
import json
import sys

# Add workspace to path to allow importing the user's script
sys.path.insert(0, r'{self.workspace_path}')

try:
    module = importlib.import_module('{module_name}')
    func = getattr(module, '{function_name}')
    
    args = {json.dumps(function_args)}
    result = func(**args)
    
    # Serialize and print the result
    print(json.dumps(result))
    
except Exception as e:
    print(f"[Execution Error] Failed to run function '{function_name}': {{e}}", file=sys.stderr)
    sys.exit(1)
"""
                        # The code to be executed is now the loader script
                        current_code = loader_code
                        print(f"📦 Created loader script to call function '{function_name}' from '{module_name}.py'")

                    except Exception as e:
                        return LocalRunnerResponse(error=f"Failed to create function loader script: {e}")

                break  # Exit the correction loop and proceed to execution
            
            # If this is the last attempt, return error with full fault log
            if attempt == max_retries - 1:
                error_parts = []
                if not package_success:
                    error_parts.append(f"package installation failed: {package_error}")
                if not syntax_success:
                    error_parts.append(f"syntax error: {syntax_error}")
                
                full_fault_log = "\n".join(fault_log)
                error_message = f"Failed to prepare code after {max_retries} attempts: {', '.join(error_parts)}\n\nFull error history:\n{full_fault_log}"
                return LocalRunnerResponse(error=error_message)
            
            # Attempt correction using error_correction.md template
            print(f"--- Issues detected. Attempting unified correction (Attempt {attempt + 1}/{max_retries}) ---")
            
            # Setup Jinja2 to load the correction prompt
            prompt_dir = os.path.join(os.path.dirname(__file__), '..', 'prompts')
            jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(prompt_dir))
            template = jinja_env.get_template("code_correction.md")
            
            # Build comprehensive error message including current attempt and full fault log
            current_error_details = []
            if not package_success:
                current_error_details.append(f"Package installation failed with error:\n{package_error}")
                current_error_details.append("Some system packages may need different conda names (e.g., 'python3-dev' -> 'python-dev', 'libssl-dev' -> 'openssl')")
            if not syntax_success:
                current_error_details.append(f"Syntax error: {syntax_error}")
            
            current_comprehensive_error = "\n".join(current_error_details)
            
            # Include fault log for historical context
            fault_log_context = "\n".join(fault_log) if fault_log else "No previous failures recorded"
            
            # Create the prompt for the LLM with accumulative context
            prompt_context = {
                "faulty_code": current_code,
                "error_message": current_comprehensive_error,
                "packages": current_packages,
                "system_packages": current_system_packages,
                "fault_log": fault_log_context,
                "attempt_number": attempt + 1,
                "total_attempts": max_retries,
                "discarded_packages": discarded_packages,
                "package_failure_counts": package_failure_counts,
                "suggestions": "provide a detailed explanation of the error and a solution to the problem, or change the code/packages to fix the error",
            }
            correction_prompt = template.render(prompt_context)
            
            # Call the LLM to get the corrected response
            response = basic_llm.invoke(correction_prompt)
            corrected_response = response.content
            
            # Try to extract corrected code and packages
            corrected_code, new_packages, new_system_packages = self._extract_code_from_llm_output(
                corrected_response, current_packages, current_system_packages
            )
            
            if corrected_code:
                current_code = corrected_code
                current_packages = new_packages
                current_system_packages = new_system_packages
                print(f"📝 Updated code and packages for retry")
                
                # Log the correction attempt
                fault_log.append(f"[Attempt {attempt + 1}] Applied LLM correction - updated code and packages")
            else:
                # Fallback: try to extract just python code if full extraction fails
                match = re.search(r"```python\s*(.*?)\s*```", corrected_response, re.DOTALL)
                if match:
                    current_code = match.group(1).strip()
                    print(f"📝 Updated code only for retry")
                    fault_log.append(f"[Attempt {attempt + 1}] Applied partial LLM correction - updated code only")
                else:
                    print(f"⚠️  Could not extract corrections from LLM response")
                    fault_log.append(f"[Attempt {attempt + 1}] LLM correction failed - could not extract valid response")
        
        # Execute the final corrected code with automatic runtime missing-package handling
        MAX_RUNTIME_RETRIES = 2
        runtime_attempt = 0
        # Reuse the same temporary script across retries to keep filesystem noise low
        script_path = None
        while runtime_attempt <= MAX_RUNTIME_RETRIES:
            try:
                # Use a temporary file to execute the code in the dedicated workspace (only create once)
                if script_path is None:
                    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py', dir=self.workspace_path) as f:
                        f.write(current_code)
                        script_path = f.name

                # Get current environment and update with .env file from the isolated .prisma directory.
                env = os.environ.copy()
                prisma_dir = os.path.dirname(self.env_path)
                dotenv_path = os.path.join(prisma_dir, ".env")
                if os.path.exists(dotenv_path):
                    env.update(dotenv_values(dotenv_path))

                # ------------------------------------------------------------------
                # Route all temporary files and workspace references to .prisma/workspace
                # ------------------------------------------------------------------
                env["PRISMA_WORKSPACE"] = self.workspace_path
                # Respect existing settings but default to workspace for temp dirs
                env.setdefault("TMPDIR", self.workspace_path)
                env.setdefault("TEMP", self.workspace_path)
                env.setdefault("TMP", self.workspace_path)

                exec_process = subprocess.run(
                    [self.python_executable, script_path], 
                    capture_output=True, 
                    text=True,
                    check=False,
                    env=env,
                    cwd=self.workspace_path
                )

                # Success path – break out of runtime retry loop
                if exec_process.returncode == 0:
                    break

                # --- Detect missing module errors (ModuleNotFoundError) ---
                missing_pkg_matches = re.findall(r"No module named ['\"]([A-Za-z0-9_\.]+)['\"]", exec_process.stderr)
                # Clean the module names (e.g., strip sub-modules like sklearn.model_selection -> sklearn)
                missing_pkgs = [m.split('.')[0] for m in missing_pkg_matches]
                if missing_pkgs and runtime_attempt < MAX_RUNTIME_RETRIES:
                    print(f"🚑 Detected missing packages at runtime: {missing_pkgs}. Attempting installation and retry ({runtime_attempt + 1}/{MAX_RUNTIME_RETRIES})...")
                    # Attempt to install missing packages and retry
                    install_success = self.install_packages(missing_pkgs, [])
                    if install_success:
                        # Track newly installed packages
                        for p in missing_pkgs:
                            if p not in current_packages:
                                current_packages.append(p)
                        runtime_attempt += 1
                        continue  # Retry execution
                    else:
                        print("❌ Failed to install packages detected at runtime. Aborting further retries.")
                # If we reach here, either no missing packages found, retries exhausted, or install failed
                break

            except Exception as e:
                # Unexpected failure during execution loop
                exec_process = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=str(e))
                break

        # After execution attempts, clean up the temporary user script if it was created
        if script_path and os.path.exists(script_path):
            os.remove(script_path)
        # Also clean up loader script if one was generated for function invocation
        if hasattr(self, 'temp_script_path') and self.temp_script_path and os.path.exists(self.temp_script_path):
            os.remove(self.temp_script_path)
            self.temp_script_path = None

        # if we switched to isolated env, restore original paths
        if use_isolated_env and tool_name:
            self.env_path = original_env_path
            self.python_executable = original_python_exec

        # Prepare the LocalRunnerResponse based on final exec_process result
        return_value = None
        if function_name and exec_process.returncode == 0:
            try:
                return_value = exec_process.stdout.strip()
            except json.JSONDecodeError:
                return_value = f"[Warning] Could not decode the function's return value from stdout."

        return LocalRunnerResponse(
            output=exec_process.stdout,
            error=exec_process.stderr if exec_process.returncode != 0 else None,
            packages=current_packages + current_system_packages,
            execution_results=[exec_process.stdout],
            return_value=return_value,
        )

    def get_environment_info(self) -> Dict[str, any]:
        """Get information about the PrismaRunEnv environment."""
        if not self.ensure_environment():
            return {"error": "Environment could not be initialized."}
        
        packages = self._get_installed_packages()
        sample_packages = list(packages)[:10]

        return {
            "name": self.env_name,
            "path": self.env_path,
            "workspace_path": self.workspace_path,
            "python_executable": self.python_executable,
            "installed_packages_count": len(packages),
            "sample_packages": sample_packages
        }

    def cleanup(self):
        """
        Does not actually clean up, as the environment is persistent.
        This method is for API consistency and to provide info.
        """
        print(f"✅ PrismaRunEnv is a persistent environment and was not removed. You can find it at: {self.env_path}")
        print(f"✅ The workspace for this environment is at: {self.workspace_path}")
    
    def __enter__(self):
        """Context manager entry."""
        self.ensure_environment()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit. Does not clean up the persistent environment."""
        pass


_persistent_env_manager_instance = None

def get_env_manager() -> PersistentEnvironmentManager:
    """
    Returns a singleton instance of the PersistentEnvironmentManager.
    
    This manager automatically ensures that:
    1. The persistent environment (PrismaRunEnv) exists
    2. All required packages are installed before any code execution
    3. Code runs in an isolated, properly configured environment
    """
    global _persistent_env_manager_instance
    if _persistent_env_manager_instance is None:
        _persistent_env_manager_instance = PersistentEnvironmentManager()
    return _persistent_env_manager_instance

# Kept for backward compatibility if anything still calls it directly.
get_persistent_env_manager = get_env_manager

def cleanup_persistent_env():
    """Provides information about the persistent environment without removing it."""
    # This function is mostly for showing information, as the env is persistent.
    env_manager = get_env_manager()
    env_manager.cleanup()



if __name__ == "__main__":
    env_manager = get_env_manager()
    response = env_manager.execute_code("""
    import pandas as pd
    df = pd.read_csv("data.csv")
    print(df.head())""", packages=["pandas"], system_packages=["python3-dev"])
    print(response.output)