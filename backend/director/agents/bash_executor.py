import logging
import subprocess

from director.agents.base import BaseAgent, AgentResponse, AgentStatus
from director.core.session import MsgStatus, TextContent

logger = logging.getLogger(__name__)


BASH_EXECUTOR_PARAMETERS = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": """Bash command to execute. Pipes, redirects, and multi-line scripts are supported.

Examples:
- 'ls -la /path/to/dir'
- 'pip install some-package'
- 'curl -s https://api.example.com | jq .'
- 'find . -name "*.py" | xargs wc -l'

Use this when you need to interact with the filesystem, install packages, run scripts, or call external CLIs.""",
        },
        "progress_message": {
            "type": "string",
            "description": "User-friendly message describing what this command does. Examples: 'Listing project files', 'Installing dependencies', 'Checking disk usage'. Keep it concise and non-technical.",
        },
        "working_directory": {
            "type": "string",
            "description": "Optional directory to run the command in. Defaults to the process's current working directory.",
        },
        "timeout": {
            "type": "integer",
            "description": "Optional timeout in seconds. Defaults to 120.",
        },
    },
    "required": ["command", "progress_message"],
}


class BashExecutorAgent(BaseAgent):
    """Executes bash commands and renders stdout/stderr/exit code."""

    def __init__(self, session, **kwargs):
        self.agent_name = "bash_executor"
        self.description = (
            "Executes bash/shell commands on the host. "
            "Returns stdout, stderr, and exit code."
        )
        self.parameters = BASH_EXECUTOR_PARAMETERS
        super().__init__(session=session, **kwargs)

    def run(
        self,
        command: str,
        progress_message: str = "",
        working_directory: str = None,
        timeout: int = 120,
        *args,
        **kwargs,
    ) -> AgentResponse:
        """Execute bash command and render output."""
        if progress_message:
            self.output_message.actions.append(progress_message)
            self.output_message.push_update()

        # Echo the command into the chat so the user sees what's running
        self.output_message.content.append(
            TextContent(
                text=f"```bash\n$ {command}\n```",
                status=MsgStatus.success,
                agent_name=self.agent_name,
                status_message="Executing bash command...",
            )
        )
        self.output_message.publish()

        try:
            logger.info(f"Executing bash command: {command}")
            result = subprocess.run(
                command,
                shell=True,
                executable="/bin/bash",
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=working_directory,
            )

            stdout = result.stdout or ""
            stderr = result.stderr or ""
            return_code = result.returncode

            # Truncate huge outputs so we don't blow up the chat / LLM context.
            stdout_display = self._truncate(stdout)
            stderr_display = self._truncate(stderr)

            parts = []
            if stdout_display:
                parts.append(f"**stdout:**\n```\n{stdout_display}\n```")
            if stderr_display:
                parts.append(f"**stderr:**\n```\n{stderr_display}\n```")
            if not stdout_display and not stderr_display:
                parts.append("_(no output)_")
            parts.append(f"**exit code:** `{return_code}`")

            success = return_code == 0
            status_message = (
                "Command executed successfully"
                if success
                else f"Command exited with code {return_code}"
            )

            return AgentResponse(
                status=AgentStatus.SUCCESS if success else AgentStatus.ERROR,
                message=status_message,
                data={
                    "stdout": stdout,
                    "stderr": stderr,
                    "return_code": return_code,
                    "command": command,
                },
            )

        except subprocess.TimeoutExpired:
            error_msg = f"Command timed out after {timeout} seconds"
            logger.exception(error_msg)
            self.output_message.content.append(
                TextContent(
                    text=f"Error: {error_msg}",
                    status=MsgStatus.error,
                    status_message="Command timed out",
                    agent_name=self.agent_name,
                )
            )
            self.output_message.publish()
            return AgentResponse(
                status=AgentStatus.ERROR,
                message=error_msg,
                data={"error": error_msg, "error_type": "TimeoutExpired"},
            )

        except Exception as e:
            logger.exception(f"Bash execution failed: {e}")
            self.output_message.content.append(
                TextContent(
                    text=f"Error: {str(e)}",
                    status=MsgStatus.error,
                    status_message="Command execution failed",
                    agent_name=self.agent_name,
                )
            )
            self.output_message.publish()
            return AgentResponse(
                status=AgentStatus.ERROR,
                message=str(e),
                data={"error": str(e), "error_type": type(e).__name__},
            )

    @staticmethod
    def _truncate(text: str, max_chars: int = 8000) -> str:
        if len(text) <= max_chars:
            return text
        head = text[: max_chars // 2]
        tail = text[-max_chars // 2 :]
        omitted = len(text) - max_chars
        return f"{head}\n\n... [{omitted} chars truncated] ...\n\n{tail}"