import logging
import queue
import threading
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from . import __version__
from .calendars import make_calendar
from .config import Settings
from .dataset import Dataset
from .extractor import OllamaExtractor
from .memory import ShortTermMemory
from .models import IncomingMessage
from .processor import Processor

log = logging.getLogger(__name__)


def build_processor(settings: Settings, extractor=None, calendar=None) -> Processor:
    return Processor(
        settings=settings,
        memory=ShortTermMemory(settings.memory_db, settings.memory_days),
        dataset=Dataset(settings.dataset_db),
        calendar=calendar or make_calendar(settings),
        extractor=extractor or OllamaExtractor(settings.ollama_host, settings.ollama_model),
    )


def create_app(settings: Settings, processor: Processor | None = None, start_background: bool = True) -> FastAPI:
    processor = processor or build_processor(settings)
    inbox: queue.Queue[IncomingMessage | None] = queue.Queue()
    stats = {"received": 0, "processed": 0}

    def worker() -> None:
        while True:
            msg = inbox.get()
            if msg is None:
                break
            try:
                processor.handle(msg)
            except Exception:
                log.exception("Unexpected error while handling message %s", msg.id)
            finally:
                stats["processed"] += 1
                inbox.task_done()

    def prune() -> None:
        removed = processor.memory.prune()
        if removed:
            log.info("Memory cleanup: deleted %d messages older than %d days", removed, settings.memory_days)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        scheduler = None
        thread = None
        if start_background:
            prune()
            scheduler = BackgroundScheduler()
            scheduler.add_job(prune, "interval", hours=1)
            scheduler.start()
            thread = threading.Thread(target=worker, name="calbot-worker", daemon=True)
            thread.start()
            log.info("Brain ready: mode=%s model=%s", settings.mode, settings.ollama_model)
        yield
        if scheduler:
            scheduler.shutdown(wait=False)
        if thread:
            inbox.put(None)

    app = FastAPI(title="WhatsApp to Calendar brain", version=__version__, lifespan=lifespan)
    app.state.inbox = inbox

    @app.get("/health")
    def health() -> dict:
        return {
            "ok": True,
            "mode": settings.mode,
            "model": settings.ollama_model,
            "queued": inbox.qsize(),
            **stats,
        }

    @app.post("/messages", status_code=202)
    def receive(msg: IncomingMessage) -> dict:
        stats["received"] += 1
        inbox.put(msg)
        return {"queued": True}

    return app
