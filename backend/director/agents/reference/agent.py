import os
import logging

from director.agents.base import BaseAgent, AgentResponse, AgentStatus

logger = logging.getLogger(__name__)

REFERENCE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "reference")

TOPICS = {
    "asset_discovery": {
        "file": "asset_discovery.md",
        "description": "Finding assets by name - resolve video/audio/image names to IDs using the /assets API with regex patterns before performing operations",
    },
    "search": {
        "file": "search.md",
        "description": "Search & indexing - spoken word index, scene index, semantic search, keyword search, search results, compiling clips from search",
    },
    "editor": {
        "file": "editor.md",
        "description": "Timeline editing - trimming, merging, VideoAsset, AudioAsset, ImageAsset, TextAsset, overlays, inline assets, CaptionAsset, styling",
    },
    "streaming": {
        "file": "streaming.md",
        "description": "Streaming & playback - HLS streams, generate_stream(), player URLs, stream from timeline/search/video",
    },
    "generative": {
        "file": "generative.md",
        "description": "AI generation - generate_image, generate_video, generate_music, generate_sound_effect, generate_voice",
    },
    "api": {
        "file": "api-reference.md",
        "description": "API reference index - cross-cutting enums (SearchType, SceneExtractionType, SubtitleStyle, TextStyle, IndexType, MediaType, Segmenter, SegmentationType, TranscodeMode, ResizeMode, ReframeMode) and exceptions (AuthenticationError, InvalidRequestError, RequestTimeoutError, SearchError, VideodbError). For methods on Connection/Collection/Video/Audio/Image, use the collection/video/audio/image topics instead",
    },
    "collection": {
        "file": "collection.md",
        "description": "Connection & Collection reference - connect, get_collection, upload, transcode, VideoConfig, AudioConfig, collection methods (search, generate_*, record_meeting, connect_rtstream), Meeting object",
    },
    "video": {
        "file": "video.md",
        "description": "Video object reference - properties, methods (generate_stream, search, add_subtitle, get_transcript, index_spoken_words, index_scenes, index_visuals, index_audio, extract_scenes, reframe, clip, insert_video, download), Reframe, SearchResult, Shot",
    },
    "audio": {
        "file": "audio.md",
        "description": "Audio object reference - properties, methods (generate_url, get_transcript, generate_transcript, delete), generating audio (music, sound effect, voice), using audio in timelines",
    },
    "image": {
        "file": "image.md",
        "description": "Image object reference - properties, methods (generate_url, delete), generating images, thumbnails, using images in timelines",
    },
    "rtstream": {
        "file": "rtstream.md",
        "description": "Live stream guide - RTSP/RTMP ingestion, real-time indexing, event detection, alerts, monitoring workflows",
    },
    "rtstream_reference": {
        "file": "rtstream-reference.md",
        "description": "RTStream SDK reference - connect_rtstream, RTStream methods, events, pipelines, webhooks",
    },
    "use_cases": {
        "file": "use-cases.md",
        "description": "Common workflows - highlight reels, searchable libraries, clip extraction, subtitles, social exports, monitoring",
    },
    "censor": {
        "file": "censor.md",
        "description": "Profanity censoring - detect profanity in transcripts, overlay beep sounds, merge overlapping timestamps, generate clean streams",
    },
}

REFERENCE_AGENT_PARAMETERS = {
    "type": "object",
    "properties": {
        "topic": {
            "type": "string",
            "description": "The reference topic to look up.",
            "enum": list(TOPICS.keys()),
        },
    },
    "required": ["topic"],
}


class ReferenceAgent(BaseAgent):
    """Returns VideoDB SDK reference documentation for a given topic."""

    def __init__(self, session, **kwargs):
        self.agent_name = "reference"
        self.description = self._build_description()
        self.parameters = REFERENCE_AGENT_PARAMETERS
        super().__init__(session=session, **kwargs)

    def _build_description(self) -> str:
        lines = ["Look up VideoDB SDK documentation. Available topics:"]
        for topic, info in TOPICS.items():
            lines.append(f"- {topic}: {info['description']}")
        return "\n".join(lines)

    def run(self, topic: str, *args, **kwargs) -> AgentResponse:
        """Return reference documentation for the given topic."""
        if topic not in TOPICS:
            return AgentResponse(
                status=AgentStatus.ERROR,
                message=f"Unknown topic: {topic}. Available: {list(TOPICS.keys())}",
            )

        self.output_message.actions.append(f"Reading reference: {topic}")
        self.output_message.push_update()

        file_path = os.path.join(REFERENCE_DIR, TOPICS[topic]["file"])

        try:
            with open(file_path, "r") as f:
                content = f.read()

            return AgentResponse(
                status=AgentStatus.SUCCESS,
                message=f"Reference for '{topic}'",
                data={"topic": topic, "content": content},
            )

        except FileNotFoundError:
            return AgentResponse(
                status=AgentStatus.ERROR,
                message=f"Reference file not found: {TOPICS[topic]['file']}",
            )
