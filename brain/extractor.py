import json
import logging
import re

import ollama

from .models import Decision
from .prompts import OUTPUT_SCHEMA, SYSTEM_PROMPT

log = logging.getLogger(__name__)


def parse_output(raw: str) -> Decision:
    """Read the model's JSON. Falls back to 'none' if the reply is broken."""
    text = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.DOTALL).strip()
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return Decision()
    try:
        return Decision.from_dict(json.loads(match.group(0)))
    except json.JSONDecodeError:
        return Decision()


class OllamaExtractor:
    def __init__(self, host: str, model: str):
        self.model = model
        self.client = ollama.Client(host=host)

    def extract(self, user_prompt: str, system_prompt: str = SYSTEM_PROMPT) -> tuple[Decision, str]:
        response = self.client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            format=OUTPUT_SCHEMA,
            options={"temperature": 0},
            keep_alive="30m",
        )
        raw = response["message"]["content"]
        return parse_output(raw), raw
