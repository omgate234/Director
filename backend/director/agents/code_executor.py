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


OUTPUT_FORMAT_INSTRUCTIONS = '''
## Output Format (MANDATORY)

Your code MUST set an `output` variable. This is a **strict contract** - the system will fail if the format is wrong.

```python
output: list[dict]  # REQUIRED - must be a list of content dicts
```

Each item in `output` MUST have a `type` field and the corresponding data field. Here are the **exact schemas**:

**Status Message:** Every content item should include a `status_message` - a brief, user-friendly title displayed above the content. Examples:
- "Found 3 matching videos"
- "Your trimmed video is ready"
- "Search results for 'artificial intelligence'"
- "Generated thumbnail"

### TextContent
```python
{
    "type": "text",           # REQUIRED: literal "text"
    "text": str,              # REQUIRED: the message to display (Markdown supported)
    "status_message": str     # RECOMMENDED: title shown above content (e.g., "Asset search results")
}
```

**Markdown Support:** The `text` field supports full GitHub-flavored Markdown - use headers, lists, tables, code blocks, bold, italic, links, etc. for rich formatting.

**Best Practice:** Use a single text block with full Markdown formatting rather than multiple text blocks. This creates a cleaner, more readable display.

```python
# GOOD: Single text block with Markdown
output = [{
    "type": "text",
    "text": """## Upload Complete

Your video has been processed successfully.

| Property | Value |
|----------|-------|
| Name | My Video |
| Duration | 120s |
| ID | m-abc123 |

**Next steps:** You can now search, edit, or add subtitles to this video."""
}]

# AVOID: Multiple fragmented text blocks
output = [
    {"type": "text", "text": "Upload Complete"},
    {"type": "text", "text": "Your video has been processed."},
    {"type": "text", "text": "Duration: 120s"}
]
```

### VideoContent
```python
{
    "type": "video",          # REQUIRED: literal "video"
    "status_message": str,    # RECOMMENDED: e.g., "Your edited video", "Uploaded successfully"
    "video": {                # REQUIRED: video data object
        "stream_url": str,    # REQUIRED: HLS stream URL
        "name": str,          # OPTIONAL: display name
        "id": str,            # OPTIONAL: video ID (m-xxx)
        "length": float,      # OPTIONAL: duration in seconds
        "thumbnail_url": str, # OPTIONAL: thumbnail image URL
        "collection_id": str, # OPTIONAL: collection ID
        "description": str    # OPTIONAL: video description
    }
}
```

### VideosContent (multiple videos)
```python
{
    "type": "videos",         # REQUIRED: literal "videos"
    "status_message": str,    # RECOMMENDED: e.g., "12 videos in your collection"
    "videos": [               # REQUIRED: list of video objects
        {
            "stream_url": str,    # REQUIRED
            "name": str,          # OPTIONAL
            "id": str,            # OPTIONAL
            "length": float,      # OPTIONAL
            "thumbnail_url": str  # OPTIONAL
        },
        # ... more videos
    ]
}
```

### ImageContent
```python
{
    "type": "image",          # REQUIRED: literal "image"
    "status_message": str,    # RECOMMENDED: e.g., "Generated thumbnail", "Extracted frame at 1:30"
    "image": {                # REQUIRED: image data object
        "url": str,           # REQUIRED: image URL - use image.generate_url() for signed URL
        "name": str,          # OPTIONAL: display name
        "id": str,            # OPTIONAL: image ID (i-xxx)
        "collection_id": str  # OPTIONAL
    }
}
```

**Note:** Always use `image.generate_url()` to get the displayable URL, not `image.url` directly.

### SearchResultsContent
```python
{
    "type": "search_results",     # REQUIRED: literal "search_results"
    "status_message": str,        # RECOMMENDED: e.g., "Found 5 mentions of 'AI'", "Search results"
    "search_results": [           # REQUIRED: list of search result objects (one per video)
        {
            "video_id": str,      # REQUIRED: video ID (m-xxx)
            "stream_url": str,    # REQUIRED: compiled clip stream URL for this video's shots
            "duration": float,    # REQUIRED: video duration in seconds — use video.length (source of truth)
            "video_title": str,   # OPTIONAL: video name
            "shots": [            # REQUIRED: list of matched shots from this video
                {
                    "start": float,       # REQUIRED: start time in seconds
                    "end": float,         # REQUIRED: end time in seconds
                    "text": str,          # REQUIRED: transcript/description text
                    "search_score": float # REQUIRED: relevance score 0-1
                }
            ]
        },
        # For collection search: additional video results...
    ]
}
```

**IMPORTANT:** `duration` is REQUIRED. Use `video.length` as the source of truth. In collection search, where you only have `Shot` objects, `shot.video_length` exposes the same value for the shot's parent video.

**Note:** For collection search, results may span multiple videos. Group shots by `video_id` and create one entry per video in `search_results`.

### Example: Correct output
```python
# Single video
output = [
    {"type": "video", "status_message": "Here is your video", "video": {"stream_url": video.stream_url, "name": video.name, "id": video.id}}
]

# Text message
output = [
    {"type": "text", "status_message": "Upload status", "text": "Upload complete!"}
]

# Multiple content items
output = [
    {"type": "text", "status_message": "Search summary", "text": "Found 3 matches:"},
    {"type": "search_results", "status_message": "Matching shots", "search_results": [...]}
]
```

### Common mistakes (will cause errors)
```python
# WRONG: missing "type" field
output = [{"video": {...}}]

# WRONG: wrong type name
output = [{"type": "vid", "video": {...}}]

# WRONG: data field doesn't match type
output = [{"type": "video", "videos": [...]}]  # should be "video" not "videos"

# WRONG: output is not a list
output = {"type": "text", "text": "..."}  # must be wrapped in list
```
'''

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
- Wrap API calls that may fail (like `get_transcript_text()`) in try/except blocks
"""
            + OUTPUT_FORMAT_INSTRUCTIONS,
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
