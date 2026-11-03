from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from brain.calendars import ShadowCalendar
from brain.config import Settings
from brain.dataset import Dataset
from brain.memory import ShortTermMemory
from brain.models import Decision, IncomingMessage
from brain.processor import Processor

IST = ZoneInfo("Asia/Kolkata")


class FakeExtractor:
    model = "fake-model"

    def __init__(self):
        self.replies: list[dict] = []
        self.prompts: list[str] = []

    def queue(self, **decision) -> None:
        self.replies.append(decision)

    def extract(self, user_prompt: str, system_prompt: str = ""):
        self.prompts.append(user_prompt)
        data = self.replies.pop(0) if self.replies else {"action": "none"}
        return Decision.from_dict({"confidence": 0.9, **data}), str(data)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path)


@pytest.fixture
def extractor() -> FakeExtractor:
    return FakeExtractor()


@pytest.fixture
def processor(settings, extractor) -> Processor:
    return Processor(
        settings=settings,
        memory=ShortTermMemory(settings.memory_db, settings.memory_days),
        dataset=Dataset(settings.dataset_db),
        calendar=ShadowCalendar(settings.shadow_db, settings.calendar_tag),
        extractor=extractor,
    )


def make_msg(body: str, when: datetime, msg_id: str | None = None, chat: str = "Dance group") -> IncomingMessage:
    return IncomingMessage(
        id=msg_id or f"{when.timestamp()}-{abs(hash(body))}",
        chat_id=f"{chat}@g.us",
        chat_name=chat,
        sender="Riya",
        body=body,
        timestamp=int(when.timestamp()),
    )
