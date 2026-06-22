import sys
import subprocess
import tempfile
import os

def run_python_script(parameters: dict, player=None) -> str:
    """
    Writes the provided Python script to a temporary file, executes it, and returns stdout/stderr.
    """
    script_code = parameters.get("script", "")
    if not script_code:
        return "Error: No script provided."

    temp_path = None
    try:
        # Create a temporary python file
        fd, temp_path = tempfile.mkstemp(suffix=".py", text=True)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(script_code)

        # Execute the script
        # Run with a timeout of 30 seconds to prevent infinite loops freezing JARVIS
        process = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Clean up the temporary file
        try:
            os.remove(temp_path)
        except Exception:
            pass

        output = ""
        if process.stdout:
            output += f"STDOUT:\n{process.stdout}\n"
        if process.stderr:
            output += f"STDERR:\n{process.stderr}\n"
            
        if not output:
            output = "Script executed successfully with no output."
            
        # Truncate output if it's too massive
        if len(output) > 2000:
            output = output[:2000] + "\n...[Output truncated due to length]"
            
        return output

    except subprocess.TimeoutExpired:
        if temp_path:
            try: os.remove(temp_path)
            except: pass
        return "Error: Script execution timed out after 30 seconds."
    except Exception as e:
        if temp_path:
            try: os.remove(temp_path)
            except: pass
        return f"Error executing script: {e}"
