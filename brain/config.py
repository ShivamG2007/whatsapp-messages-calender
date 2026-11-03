import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _ollama_host() -> str:
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").strip().replace("0.0.0.0", "127.0.0.1")
    return host if host.startswith("http") else f"http://{host}"


@dataclass
class Settings:
    mode: str = "shadow"
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "calbot-base"
    bridge_host: str = "127.0.0.1"
    bridge_port: int = 8765
    timezone: str = "Asia/Kolkata"
    memory_days: int = 2
    context_messages: int = 15
    min_confidence: float = 0.6
    default_event_minutes: int = 60
    lookahead_days: int = 45
    calendar_tag: str = "CalBot"
    ms_client_id: str = ""
    data_dir: Path = field(default_factory=lambda: ROOT / "data")

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    @property
    def memory_db(self) -> Path:
        return self.data_dir / "memory.db"

    @property
    def dataset_db(self) -> Path:
        return self.data_dir / "dataset.db"

    @property
    def shadow_db(self) -> Path:
        return self.data_dir / "shadow_calendar.db"

    @property
    def token_cache(self) -> Path:
        return self.data_dir / "ms_token_cache.json"

    @property
    def live(self) -> bool:
        return self.mode == "live"


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env", override=True)
    mode = os.getenv("MODE", "shadow").strip().lower()
    if mode not in {"shadow", "live"}:
        raise ValueError(f"MODE must be 'shadow' or 'live', got {mode!r}")
    data_dir = Path(os.getenv("DATA_DIR", ROOT / "data"))
    if not data_dir.is_absolute():
        data_dir = ROOT / data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        mode=mode,
        ollama_host=_ollama_host(),
        ollama_model=os.getenv("OLLAMA_MODEL", "calbot-base"),
        bridge_host=os.getenv("BRIDGE_HOST", "127.0.0.1"),
        bridge_port=_int("BRIDGE_PORT", 8765),
        timezone=os.getenv("TIMEZONE", "Asia/Kolkata"),
        memory_days=_int("MEMORY_DAYS", 2),
        context_messages=_int("CONTEXT_MESSAGES", 15),
        min_confidence=_float("MIN_CONFIDENCE", 0.6),
        default_event_minutes=_int("DEFAULT_EVENT_MINUTES", 60),
        lookahead_days=_int("LOOKAHEAD_DAYS", 45),
        calendar_tag=os.getenv("CALENDAR_TAG", "CalBot"),
        ms_client_id=os.getenv("MS_CLIENT_ID", "").strip(),
        data_dir=data_dir,
    )
