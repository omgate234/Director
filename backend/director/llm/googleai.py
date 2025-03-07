import json
from enum import Enum

from pydantic import Field, field_validator, FieldValidationInfo
from pydantic_settings import SettingsConfigDict

from director.core.session import RoleTypes
from director.llm.base import BaseLLM, BaseLLMConfig, LLMResponse, LLMResponseStatus
from director.constants import (
    LLMType,
    EnvPrefix,
)


class GoogleChatModel(str, Enum):
    """Enum for Google Gemini Chat models"""

    GEMINI_1_5_FLASH = "gemini-1.5-flash"
    GEMINI_1_5_FLASH_0_0_2 = "gemini-1.5-flash-002"
    GEMINI_1_5_PRO = "gemini-1.5-pro"
    GEMINI_1_5_PRO_0_0_2 = "gemini-1.5-pro-002"
    GEMINI_2_0_FLASH = "gemini-2.0-flash"
    GEMINI_2_0_FLASH_0_0_1 = "gemini-2.0-flash-001"
    GEMINI_2_0_PRO = "gemini-2.0-pro-exp"


class GoogleAIConfig(BaseLLMConfig):
    """GoogleAI Config"""

    model_config = SettingsConfigDict(
        env_prefix=EnvPrefix.GOOGLEAI_,
        extra="ignore",
    )

    llm_type: str = LLMType.GOOGLEAI
    api_key: str = ""
    api_base: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    chat_model: str = Field(default=GoogleChatModel.GEMINI_2_0_FLASH)
    max_tokens: int = 4096

    @field_validator("api_key")
    @classmethod
    def validate_non_empty(cls, v, info: FieldValidationInfo):
        if not v:
            raise ValueError(
                f"{info.field_name} must not be empty. Please set {EnvPrefix.GOOGLEAI_.value}{info.field_name.upper()} environment variable."
            )
        return v


class GoogleAI(BaseLLM):
    def __init__(self, config: GoogleAIConfig = None):
        """
        :param config: GoogleAI Config
        """
        if config is None:
            config = GoogleAIConfig()
        super().__init__(config=config)
        try:
            import openai
        except ImportError:
            raise ImportError("Please install OpenAI python library.")

        self.client = openai.OpenAI(
            api_key=self.api_key, base_url=self.api_base
        )

    def _format_messages(self, messages: list):
        """Format the messages to the format that Google Gemini expects."""
        formatted_messages = []

        if messages and messages[0]["role"] == RoleTypes.system.value:
            messages = messages[1:]

        for message in messages:
            message["content"] = message.get("content", "") or ""

            if message["role"] == RoleTypes.assistant.value and message.get(
                "tool_calls"
            ):
                formatted_messages.append(
                    {
                        "role": message["role"],
                        "content": message["content"],
                        "tool_calls": [
                            {
                                "id": tool_call["id"],
                                "function": {
                                    "name": tool_call.get("tool", {}).get("name", ""),
                                    "arguments": json.dumps(
                                        tool_call.get("tool", {}).get("arguments", {})
                                    ),
                                },
                                "type": tool_call["type"],
                            }
                            for tool_call in message["tool_calls"]
                        ],
                    }
                )
            elif message["role"] == RoleTypes.tool.value:
                formatted_messages.append(
                    {
                        "role": RoleTypes.tool.value,
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": message["tool_call_id"],
                                "content": message["content"],
                            }
                        ],
                    }
                )
            else:
                formatted_messages.append(message)

        return formatted_messages

    def _format_tools(self, tools: list):
        """Format the tools to the format that Gemini expects."""
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {}),
                },
            }
            for tool in tools
            if tool.get("name")
        ]

    def chat_completions(
        self, messages: list, tools: list = [], response_format=None
    ):
        """Get chat completions using Gemini."""
        params = {
            "model": self.chat_model,
            "messages": self._format_messages(messages),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
        }

        if tools:
            params["tools"] = self._format_tools(tools)
            params["tool_choice"] = "auto"

        if response_format:
            params["response_format"] = response_format

        try:
            response = self.client.chat.completions.create(**params)
        except Exception as e:
            print(f"Error: {e}")
            return LLMResponse(content=f"Error: {e}")

        choice = response.choices[0] if response.choices else None
        content = (
            choice.message.content
            if choice and choice.message.content
            else "No response"
        )

        tool_calls = (
            [
                {
                    "id": tc.id,
                    "tool": {
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments),
                    },
                    "type": tc.type,
                }
                for tc in choice.message.tool_calls
            ]
            if choice and choice.message.tool_calls
            else []
        )

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason if choice else "",
            status=LLMResponseStatus.SUCCESS,
        )
