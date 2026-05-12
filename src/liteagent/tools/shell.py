import subprocess

def run_shell_command(command: str, timeout: int = 60) -> str:
    """
    Executes a shell command (CMD/PowerShell on Windows, bash/sh on Unix) and returns its output.
    
    Args:
        command: The shell command to execute.
        timeout: Maximum execution time in seconds. Defaults to 60.
    """
    try:
        # shell=True runs the command through the system shell
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        output = []
        output.append(f"Exit Code: {result.returncode}")
        
        if result.stdout:
            output.append("--- Stdout ---")
            output.append(result.stdout.strip())
            
        if result.stderr:
            output.append("--- Stderr ---")
            output.append(result.stderr.strip())
            
        if not result.stdout and not result.stderr:
            output.append("(No output)")
            
        return "\n".join(output)
        
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout} seconds."
    except Exception as e:
        return f"Error executing command: {str(e)}"
