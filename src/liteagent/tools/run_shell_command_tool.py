import subprocess
from .providers import ToolProviderFactory

def create_run_shell_command_tool(providers: ToolProviderFactory):
    def run_shell_command(command: str, timeout: int = 60) -> str:
        """Executes a shell command and returns the stdout and stderr."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            output = ""
            if result.stdout:
                output += f"STDOUT:\n{result.stdout}\n"
            if result.stderr:
                output += f"STDERR:\n{result.stderr}\n"
            if not output:
                output = "Command executed successfully with no output."
            return output
        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {timeout} seconds."
        except Exception as e:
            return f"Error executing command: {str(e)}"
    return run_shell_command
