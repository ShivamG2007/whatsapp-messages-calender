import argparse
import json
import logging
import sys
import time
import uuid
from datetime import datetime, timedelta

from . import __version__
from .config import load_settings


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("httpx", "apscheduler", "msal", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def cmd_serve(settings, args) -> None:
    import uvicorn

    from .server import create_app

    uvicorn.run(create_app(settings), host=settings.bridge_host, port=settings.bridge_port, log_level="warning")


def cmd_login(settings, args) -> None:
    from .calendars import GraphAuth

    who = GraphAuth(settings.ms_client_id, settings.token_cache).login()
    print(f"Signed in as {who}. The token is saved in {settings.token_cache.name} (never commit this file).")


def cmd_check(settings, args) -> None:
    import ollama

    print(f"Mode: {settings.mode}")
    try:
        names = [m.model for m in ollama.Client(host=settings.ollama_host).list().models]
        found = any(n == settings.ollama_model or n.startswith(settings.ollama_model + ":") for n in names)
        print(f"Ollama: reachable, model '{settings.ollama_model}' {'found' if found else 'NOT FOUND'}")
    except Exception as exc:
        print(f"Ollama: NOT reachable at {settings.ollama_host} ({exc})")
    if settings.live:
        from .calendars import make_calendar

        try:
            now = datetime.now(settings.tz)
            events = make_calendar(settings).list_events(now, now + timedelta(days=7))
            print(f"Outlook: connected, {len(events)} bot events in the next 7 days")
        except Exception as exc:
            print(f"Outlook: problem: {exc}")
    else:
        print("Outlook: not used in shadow mode")


def cmd_try(settings, args) -> None:
    from .dataset import Dataset
    from .models import IncomingMessage
    from .server import build_processor

    processor = build_processor(settings)
    processor.dataset = Dataset(settings.data_dir / "try_dataset.db")
    sent = datetime.now(settings.tz) if not args.at else datetime.fromisoformat(args.at).replace(tzinfo=settings.tz)
    msg = IncomingMessage(
        id=f"manual-{uuid.uuid4().hex[:10]}",
        chat_id=f"manual:{args.chat}",
        chat_name=args.chat,
        sender=args.sender,
        body=args.message,
        timestamp=int(sent.timestamp()),
    )
    started = time.perf_counter()
    outcome = processor.handle(msg)
    print(json.dumps(outcome.to_dict(), indent=2, ensure_ascii=False))
    print(f"({time.perf_counter() - started:.1f}s, mode={settings.mode})")


def cmd_events(settings, args) -> None:
    from .calendars import make_calendar

    now = datetime.now(settings.tz)
    events = make_calendar(settings).list_events(now - timedelta(days=args.past), now + timedelta(days=settings.lookahead_days))
    if not events:
        print("No bot events.")
    for event in events:
        print(f"- {event.summary()}")


def cmd_prune(settings, args) -> None:
    from .memory import ShortTermMemory

    removed = ShortTermMemory(settings.memory_db, settings.memory_days).prune()
    print(f"Deleted {removed} messages older than {settings.memory_days} days.")


def cmd_stats(settings, args) -> None:
    from .dataset import Dataset
    from .memory import ShortTermMemory

    print(f"Messages in short-term memory: {ShortTermMemory(settings.memory_db, settings.memory_days).count()}")
    print(json.dumps(Dataset(settings.dataset_db).stats(), indent=2))


def cmd_export_labelstudio(settings, args) -> None:
    from .dataset import Dataset
    from .training import export_label_studio

    out = args.out or settings.data_dir / "exports" / "labelstudio_tasks.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    n = export_label_studio(Dataset(settings.dataset_db), out, include_labeled=args.all)
    print(f"Wrote {n} tasks to {out}")


def cmd_import_labelstudio(settings, args) -> None:
    from .dataset import Dataset
    from .training import import_label_studio

    counts = import_label_studio(Dataset(settings.dataset_db), args.file)
    print(dict(counts))


def cmd_export_llamafactory(settings, args) -> None:
    from .dataset import Dataset
    from .training import export_llamafactory

    out = args.out or settings.data_dir / "exports" / "llamafactory"
    counts = export_llamafactory(Dataset(settings.dataset_db), out)
    print(f"Wrote {counts['train']} train and {counts['test']} test examples to {out}")


def cmd_evaluate(settings, args) -> None:
    from .dataset import Dataset
    from .extractor import OllamaExtractor
    from .training import evaluate

    model = args.model or settings.ollama_model
    report = evaluate(Dataset(settings.dataset_db), OllamaExtractor(settings.ollama_host, model), args.split, args.limit)
    print(f"Model: {model}")
    print(json.dumps(report, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> None:
    from pathlib import Path

    parser = argparse.ArgumentParser(prog="python -m brain", description="WhatsApp to Outlook calendar brain")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("serve", help="start the bridge the WhatsApp listener sends messages to").set_defaults(func=cmd_serve)
    sub.add_parser("login", help="sign in to your personal Outlook (one time)").set_defaults(func=cmd_login)
    sub.add_parser("check", help="check Ollama and Outlook are reachable").set_defaults(func=cmd_check)

    p = sub.add_parser("try", help="run one made-up message through the whole pipeline")
    p.add_argument("message")
    p.add_argument("--chat", default="Test group")
    p.add_argument("--sender", default="Tester")
    p.add_argument("--at", help="pretend send time, e.g. 2026-11-04T18:30")
    p.set_defaults(func=cmd_try)

    p = sub.add_parser("events", help="list events the bot created")
    p.add_argument("--past", type=int, default=1, help="also show events from this many past days")
    p.set_defaults(func=cmd_events)

    sub.add_parser("prune", help="delete memory older than MEMORY_DAYS now").set_defaults(func=cmd_prune)
    sub.add_parser("stats", help="show memory and dataset counts").set_defaults(func=cmd_stats)

    p = sub.add_parser("export-labelstudio", help="write unlabeled records as Label Studio tasks")
    p.add_argument("--out", type=Path)
    p.add_argument("--all", action="store_true", help="include records you already labeled")
    p.set_defaults(func=cmd_export_labelstudio)

    p = sub.add_parser("import-labelstudio", help="read your labels back from a Label Studio JSON export")
    p.add_argument("file", type=Path)
    p.set_defaults(func=cmd_import_labelstudio)

    p = sub.add_parser("export-llamafactory", help="write labeled data in LLaMA-Factory format")
    p.add_argument("--out", type=Path)
    p.set_defaults(func=cmd_export_llamafactory)

    p = sub.add_parser("evaluate", help="score a model on labeled test examples")
    p.add_argument("--model", help="Ollama model name (default: OLLAMA_MODEL)")
    p.add_argument("--split", default="test", choices=["train", "test"])
    p.add_argument("--limit", type=int)
    p.set_defaults(func=cmd_evaluate)

    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    try:
        settings = load_settings()
    except ValueError as exc:
        sys.exit(f"Config error: {exc}")
    args.func(settings, args)


if __name__ == "__main__":
    main()
