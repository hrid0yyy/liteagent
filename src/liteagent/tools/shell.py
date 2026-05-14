import asyncio
import sys
from typing import Optional, Callable, Awaitable

async def run_shell_command(
    command: str, 
    timeout: int = 60, 
    on_output: Optional[Callable[[str], None]] = None
) -> str:
    """
    Executes a shell command asynchronously and returns its output.
    
    Args:
        command: The shell command to execute.
        timeout: Maximum execution time in seconds. Defaults to 60.
        on_output: Optional callback function called with each line of output.
    """
    try:
        # Use the appropriate shell for the platform
        shell = "powershell.exe" if sys.platform == "win32" else None
        
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            executable=shell
        )

        stdout_lines = []
        stderr_lines = []

        async def read_stream(stream, collection, is_stderr=False):
            while True:
                line = await stream.readline()
                if not line:
                    break
                decoded_line = line.decode('utf-8', errors='replace').rstrip()
                collection.append(decoded_line)
                if on_output:
                    prefix = "[red]Error: [/red]" if is_stderr else ""
                    on_output(f"{prefix}{decoded_line}")

        try:
            # Wait for both streams and the process to finish with a timeout
            await asyncio.wait_for(
                asyncio.gather(
                    read_stream(process.stdout, stdout_lines),
                    read_stream(process.stderr, stderr_lines, is_stderr=True)
                ),
                timeout=timeout
            )
            return_code = await process.wait()
        except asyncio.TimeoutExpired:
            try:
                process.kill()
            except:
                pass
            return f"Error: Command timed out after {timeout} seconds."

        output = []
        output.append(f"Exit Code: {return_code}")
        
        if stdout_lines:
            output.append("--- Stdout ---")
            output.append("\n".join(stdout_lines))
            
        if stderr_lines:
            output.append("--- Stderr ---")
            output.append("\n".join(stderr_lines))
            
        if not stdout_lines and not stderr_lines:
            output.append("(No output)")
            
        return "\n".join(output)
        
    except Exception as e:
        return f"Error executing command: {str(e)}"

