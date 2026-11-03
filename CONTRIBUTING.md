# Contributing

Thanks for helping. A few ground rules first, because this project handles private chats:

- **Never** put real messages, names, phone numbers, chat ids, tokens or `.env` contents in issues, PRs, tests or commits. Make up examples instead.
- The listener must stay **read-only**: no code that sends WhatsApp messages.
- The bot must only edit or delete calendar events it created.

## Dev setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
cd listener; npm install; cd ..
```

## Before opening a PR

```powershell
ruff format .
ruff check .
pytest
cd listener; npm test; cd ..
```

- Add a test for any new date/time rule (`tests/test_dates.py`) or decision rule (`tests/test_processor.py`).
- If you change `SYSTEM_PROMPT`, bump `PROMPT_VERSION` in `brain/prompts.py`.
- Add a line to `CHANGELOG.md` under *Unreleased*.

## Commit messages

Short and in the imperative: `Handle "parso" as day after tomorrow`, `Skip events already over`.
