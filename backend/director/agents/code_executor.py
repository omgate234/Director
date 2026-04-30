import logging

from director.agents.base import BaseAgent, AgentResponse, AgentStatus
from director.core.session import (
    MsgStatus,
    TextContent,
    VideoContent,
    VideoData,
    ImageContent,
    ImageData,
    VideosContent,
    SearchResultsContent,
    SearchData,
    ShotData,
)

logger = logging.getLogger(__name__)


CODE_EXECUTOR_PARAMETERS = {
    "type": "object",
    "properties": {
        "code": {
            "type": "string",
            "description": """Python code to execute. Must set `output` variable to a list of content dicts.

How you read results back:
- The ONLY way to surface a value from this script to yourself (and to the user) is by assigning it into the `output` variable. `print(...)`, `logging`, stdout, and stderr are NOT captured and NOT returned — you will not see them. If you want to inspect an intermediate value (an asset ID, a video's length, a count of matches, etc.), put it into `output` as a text content item.

Code execution environment:
- `conn` (VideoDB connection) is pre-defined and available
- All code runs in a single flat namespace (no separate globals/locals)
- Standard library imports are allowed (e.g., `import re`, `from videodb import SearchType`)

Gotchas to avoid:
- Always initialize variables before using them in comprehensions or generator expressions
- For video names with special characters (|, &, []), prefer keyword-based search over full regex escaping
- Wrap API calls that may fail (like `get_transcript_text()`) in try/except blocks""",
        },
        "progress_message": {
            "type": "string",
            "description": "User-friendly message describing what this code does. Examples: 'Finding videos matching \"podcast\"', 'Searching for mentions of AI', 'Trimming video to selected segment', 'Adding subtitles to your video'. Keep it concise and non-technical.",
        },
    },
    "required": ["code", "progress_message"],
}


class CodeExecutorAgent(BaseAgent):
    """Executes VideoDB Python code and renders output."""

    def __init__(self, session, **kwargs):
        self.agent_name = "code_executor"
        self.description = "Executes VideoDB Python code. Code must set `output` variable with list of content dicts."
        self.parameters = CODE_EXECUTOR_PARAMETERS
        super().__init__(session=session, **kwargs)

    def run(self, code: str, progress_message: str = "", *args, **kwargs) -> AgentResponse:
        """Execute code and render output."""
        if progress_message:
            self.output_message.actions.append(progress_message)
            self.output_message.push_update()

        self.output_message.content.append(
            TextContent(
                text=f"```python\n{code}\n```",
                status=MsgStatus.success,
                agent_name=self.agent_name,
            )
        )
        self.output_message.publish()

        output = []
        try:
            conn = self.session.state.get("conn")
            if not conn:
                raise ValueError("No VideoDB connection available")

            # Use single namespace for both globals and locals.
            # Separate dicts break comprehensions/generators (they create new scopes
            # that inherit from globals, not locals, causing NameError).
            exec_namespace = {
                "conn": conn,
                "__builtins__": __builtins__,
            }

            logger.info(f"Executing code:\n{code}")
            exec(code, exec_namespace)

            output = exec_namespace.get("output")
            if output is None:
                raise ValueError("Code must set an 'output' variable")

            content_list = self._render_output(output)

            self.output_message.publish()

            return AgentResponse(
                status=AgentStatus.SUCCESS,
                message="Code executed successfully",
                data={"content": content_list},
            )

        except Exception as e:
            logger.exception(f"Code execution failed: {e}")
            self.output_message.content.append(
                TextContent(
                    text=f"Error: {str(e)}",
                    status=MsgStatus.error,
                    status_message="Code execution failed",
                    agent_name=self.agent_name,
                )
            )
            self.output_message.publish()

            return AgentResponse(
                status=AgentStatus.ERROR,
                message=str(e),
                data={"error": str(e), "error_type": type(e).__name__, "output": output},
            )

    def _render_output(self, output: list) -> list:
        """Render output list to message content."""
        content_list = []

        for item in output:
            content_type = item.get("type")
            status_message = item.get("status_message")

            if content_type == "text":
                content = TextContent(
                    text=item.get("text", ""),
                    status=MsgStatus.success,
                    status_message=status_message,
                    agent_name=self.agent_name,
                )
                self.output_message.content.append(content)
                content_list.append(content.model_dump())

            elif content_type == "video":
                video_data = item.get("video", {})
                content = VideoContent(
                    video=VideoData(**video_data),
                    status=MsgStatus.success,
                    status_message=status_message,
                    agent_name=self.agent_name,
                )
                self.output_message.content.append(content)
                content_list.append(content.model_dump())

            elif content_type == "videos":
                videos = [VideoData(**v) for v in item.get("videos", [])]
                content = VideosContent(
                    videos=videos,
                    status=MsgStatus.success,
                    status_message=status_message,
                    agent_name=self.agent_name,
                )
                self.output_message.content.append(content)
                content_list.append(content.model_dump())

            elif content_type == "image":
                image_data = item.get("image", {})
                content = ImageContent(
                    image=ImageData(**image_data),
                    status=MsgStatus.success,
                    status_message=status_message,
                    agent_name=self.agent_name,
                )
                self.output_message.content.append(content)
                content_list.append(content.model_dump())

            elif content_type == "search_results":
                search_results = []
                for sr in item.get("search_results", []):
                    shots = [ShotData(**s) for s in sr.get("shots", [])]
                    search_results.append(
                        SearchData(
                            video_id=sr.get("video_id", ""),
                            video_title=sr.get("video_title"),
                            stream_url=sr.get("stream_url", ""),
                            duration=sr.get("duration", 0),
                            shots=shots,
                        )
                    )
                content = SearchResultsContent(
                    search_results=search_results,
                    status=MsgStatus.success,
                    status_message=status_message,
                    agent_name=self.agent_name,
                )
                self.output_message.content.append(content)
                content_list.append(content.model_dump())

        self.output_message.push_update()
        return content_list
