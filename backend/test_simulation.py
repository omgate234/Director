import json
import csv
from typing import List
import time

from director.core.session import Session, ContextMessage
from director.db import load_db
from director.agents.base import BaseAgent
from director.llm.googleai import GoogleAI

def load_agents(session: Session) -> List[BaseAgent]:
    """Load all available agents."""
    from director.agents.thumbnail import ThumbnailAgent
    from director.agents.summarize_video import SummarizeVideoAgent
    from director.agents.download import DownloadAgent
    from director.agents.pricing import PricingAgent
    from director.agents.upload import UploadAgent
    from director.agents.search import SearchAgent
    from director.agents.prompt_clip import PromptClipAgent
    from director.agents.index import IndexAgent
    from director.agents.brandkit import BrandkitAgent
    from director.agents.profanity_remover import ProfanityRemoverAgent
    from director.agents.image_generation import ImageGenerationAgent
    from director.agents.audio_generation import AudioGenerationAgent
    from director.agents.video_generation import VideoGenerationAgent
    from director.agents.stream_video import StreamVideoAgent
    from director.agents.subtitle import SubtitleAgent
    from director.agents.slack_agent import SlackAgent
    from director.agents.editing import EditingAgent
    from director.agents.dubbing import DubbingAgent
    from director.agents.text_to_movie import TextToMovieAgent
    from director.agents.meme_maker import MemeMakerAgent
    from director.agents.composio import ComposioAgent
    from director.agents.transcription import TranscriptionAgent
    from director.agents.comparison import ComparisonAgent
    from director.agents.web_search_agent import WebSearchAgent

    agents = [
        ThumbnailAgent,
        SummarizeVideoAgent,
        DownloadAgent,
        PricingAgent,
        UploadAgent,
        SearchAgent,
        PromptClipAgent,
        IndexAgent,
        BrandkitAgent,
        ProfanityRemoverAgent,
        ImageGenerationAgent,
        AudioGenerationAgent,
        VideoGenerationAgent,
        StreamVideoAgent,
        SubtitleAgent,
        SlackAgent,
        EditingAgent,
        DubbingAgent,
        TranscriptionAgent,
        TextToMovieAgent,
        MemeMakerAgent,
        ComposioAgent,
        ComparisonAgent,
        WebSearchAgent,
    ]
    
    return [agent(session=session) for agent in agents]

def process_example(example: dict, db):
    """Process a single example through the Director's flow."""
    llm = GoogleAI()
    
    print(f"\nProcessing example with session_id: {example['session_id']}")
    
    session = Session(db=db, session_id=example['session_id'], conv_id=example['conv_id'])
    
    all_agents = load_agents(session)
    agents_mapping = {agent.name: agent for agent in all_agents}
    
    final_agents = []
    if json.loads(example['input_agents']):
        for agent_name in json.loads(example['input_agents']):
            if agent_name in agents_mapping:
                final_agents = [agents_mapping[agent_name]]
    else:
        final_agents = all_agents
    
    reasoning_context = [
        ContextMessage.from_json(msg) for msg in json.loads(example['reasoning_context'])
    ]

    time.sleep(2)
    output = llm.chat_completions(
        messages=[message.to_llm_msg() for message in reasoning_context],
        tools=[agent.to_llm_format() for agent in final_agents],
    )
    
    return {
        "gemini_0_5_chat_content": output.content,
        "gemini_0_5_tool_calls": output.tool_calls
    }

def main():
    input_filename = "updated_filtered_conversation_2.json"
    output_filename = "updated_filtered_conversation_3.json"
    
    with open(input_filename, "r") as f:
        examples = json.load(f)

    db = load_db()
    
    updated_results = []

    for example in examples:
        try:
            new_fields = process_example(example, db)
            updated_example = {**example, **new_fields}  # Merge original fields with new ones
            updated_results.append(updated_example)
        except Exception as e:
            print(f"Error processing example {example['session_id']}: {str(e)}")

    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(updated_results, f, indent=4)

    print(f"Updated results saved to {output_filename}")

if __name__ == "__main__":
    main()
