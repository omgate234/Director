import json
import csv
from typing import List
import time

from director.core.session import Session, ContextMessage
from director.db import load_db
from director.llm.googleai import GoogleAI
from director.llm.openai import OpenAI
from director.core.session import RoleTypes

EVALUATOR_PROMPT = """
You are an AI evaluator. Your task is to compare the outputs of different LLM models and analyze their performance against an existing system's response. The results must be returned in a structured JSON format to allow numerical comparison.

You will analyze the outputs from three different models:

Gemini-2.0-Flash (temp: 1)

gemini_1_chat_content: Text response
gemini_1_tool_calls: Tool calls
Gemini-2.0-Flash (temp: 0.7)

gemini_0_7_chat_content: Text response
gemini_0_7_tool_calls: Tool calls
Gemini-2.0-Flash (temp: 0.5)

gemini_0_5_chat_content: Text response
gemini_0_5_tool_calls: Tool calls
Comparison Criteria:
For each model, evaluate the response based on the following criteria, scoring each on a scale of 0 to 1:

Tool Selection

Did the model choose the correct tools?
Do the selected tools match output_agents?
Did the tools fulfill the user's request?
Reasoning

Did the model logically analyze and select the appropriate response?
Was its reasoning contextually correct?
Response Quality

How clear, relevant, and complete was the response?
If a text response was given, was it informative and well-structured?
Trajectory

How much did the response deviate from the main topic?
A score closer to 1 means minimal deviation; closer to 0 means the response strayed significantly.
Output Format (JSON):
Return a JSON object structured as follows:

```
{
  "gemini_1": {
    "tool_selection": 0.85,
    "reasoning": 0.90,
    "response_quality": 0.80,
    "trajectory": 0.95
  },
  "gemini_0_7": {
    "tool_selection": 0.80,
    "reasoning": 0.85,
    "response_quality": 0.75,
    "trajectory": 0.90
  },
  "gemini_0_5": {
    "tool_selection": 0.75,
    "reasoning": 0.80,
    "response_quality": 0.70,
    "trajectory": 0.85
  },
  "best_model": "gemini_1",
  "at_par_or_better_than_existing": true
}
```
Where:

"best_model" indicates the model with the highest overall performance.
"at_par_or_better_than_existing" is true if any Gemini model matches or outperforms the original system's output, otherwise false.
"""


 

def process_example(example: dict):
    """Process a single example and return the evaluation result."""
    llm = OpenAI()

    system_prompt = ContextMessage(
        content=EVALUATOR_PROMPT,
        role=RoleTypes.system,
    )

    evaluation_data = ContextMessage(
        content=json.dumps(example),
        role=RoleTypes.user,
    )

    llm_response = llm.chat_completions(
        [system_prompt.to_llm_msg(), evaluation_data.to_llm_msg()],
        response_format={"type": "json_object"},
    )

    output = json.loads(llm_response.content)  # Extract JSON output

    return {
        "session_id": example["session_id"],
        "conv_id": example["conv_id"],
        "output": output,
    }


def main():
    input_filename = "updated_filtered_conversation_3.json"
    output_filename = "evaluation_results.json"

    with open(input_filename, "r") as f:
        examples = json.load(f)

    results = []
    for example in examples:
        try:
            result = process_example(example)
            results.append(result)
        except Exception as e:
            print(f"Error processing example {example['session_id']}: {str(e)}")

    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4)

    print(f"Evaluation results saved to {output_filename}")


if __name__ == "__main__":
    main()