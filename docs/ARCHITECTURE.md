# Architecture

## Two processes

| Part | Language | Why |
|---|---|---|
| `listener/` | Node.js | whatsapp-web.js only exists for Node. This part is kept tiny: it reads and forwards, nothing else. |
| `brain/` | Python | Ollama, dateparser, Microsoft sign-in (MSAL) and all the ML tooling are Python. |

They talk over HTTP on `127.0.0.1:8765` (`POST /messages`, `GET /health`). Nothing is exposed outside the laptop.

## Life of one message

```
WhatsApp ──► listener: is the chat in config/selected_chats.json? ── no ──► ignored
                │ yes
                ▼
        POST /messages ──► queue ──► worker thread (one message at a time, in order)
                                        │
                     1. save to short-term memory (data/memory.db)
                     2. keyword prefilter ("ok", "lol" stop here)
                     3. read upcoming bot events from the calendar
                     4. build prompt: message + last 2 days of the group + numbered events
                     5. Ollama ──► JSON {action, event, date_text, time_text, place, target, confidence}
                     6. dateparser + time rules ──► real start/end
                     7. safety checks ──► create / update / delete (shadow or Outlook)
                     8. save everything to the dataset (data/dataset.db)
```

## Why the model copies words instead of dates

A 4B model is good at reading "kal shaam 6 baje" but unreliable at arithmetic like "Wednesday + 1 day". In testing it answered `2026-11-08` for "tomorrow" on 4 Nov. So the model only returns `date_text: "kal"`, `time_text: "shaam 6"`, and `brain/dates.py` does the arithmetic. This also makes the training target simpler.

Rules in `dates.py`:
- `kal` = tomorrow, `aaj`/`tonight` = today, `parso` = day after tomorrow
- "friday" / "next friday" / "this friday" = the coming Friday. Today's weekday name means today.
- A bare hour 1–7 = PM, and 8–11 = AM. `shaam`/`evening`/`raat` force PM, `subah`/`morning` force AM.
- Time with no date: today, or tomorrow if that time has already passed.
- Date with no time: all-day event.
- Reschedule that only gives a new time keeps the old date (and the reverse). The duration is kept unless a new end time is given.

## Two stores, one long-term memory

| Store | File | Kept | Used for |
|---|---|---|---|
| Short-term memory | `data/memory.db` | `MEMORY_DAYS` (2), pruned hourly | Context for the prompt |
| Dataset | `data/dataset.db` | Forever | Labeling, training, evaluation |
| Calendar description | Outlook / `data/shadow_calendar.db` | As long as the event exists | Long-term memory: which group, original message, history of changes |

A bot event's description looks like:

```
[CalBot] auto-added from WhatsApp, edits to the text below may confuse the bot
chat: Dance group
chat_id: 1203...@g.us
source_message_id: false_1203...
source_message: guys dance practice tomorrow 6pm at OAT
sent_at: 2026-11-04 10:00
history:
- 2026-11-04 10:00 added (message from Riya: guys dance practice tomorrow 6pm at OAT)
- 2026-11-04 11:00 changed from [Dance practice | Thu 2026-11-05 18:00 | OAT] (message from Riya: shifted to 7)
```

When "Saturday match cancelled" arrives a week later, the 2-day memory is long gone. The bot still sees the event in the calendar, knows which group it came from, and can delete it.

## Shadow vs live

`MODE=shadow` writes to `ShadowCalendar`, a SQLite file with the same interface as Outlook. Add → reschedule → cancel chains behave exactly as they will in live mode, and nothing touches your real calendar. `MODE=live` switches to `OutlookCalendar` (Microsoft Graph).

## Safety checks

- Only chats in `selected_chats.json` are read. The listener has no code path that sends messages.
- `confidence < MIN_CONFIDENCE` → skipped.
- Cancel/reschedule must match an existing **bot** event: first the model's `target` number, then a title match in the same group, then "the only bot event from this group". Otherwise the message is skipped (cancel) or the event is added (reschedule).
- Before any update/delete in Outlook, the event is fetched again and must carry both the `CalBot` category and the `[CalBot]` description.
- The same event announced twice (same group, similar title, same day) is not added twice.
- Events already over when the message arrives are not added.

## Files

| File | Job |
|---|---|
| `brain/server.py` | FastAPI bridge, worker thread, hourly memory cleanup |
| `brain/processor.py` | The pipeline and all decision rules |
| `brain/prompts.py` | System prompt, JSON schema, prompt builder (bump `PROMPT_VERSION` when you change it) |
| `brain/extractor.py` | Ollama call with structured JSON output |
| `brain/dates.py` | Date and time words → datetimes |
| `brain/memory.py` | 2-day message store |
| `brain/dataset.py` | Permanent training data store |
| `brain/training.py` | Label Studio import/export, LLaMA-Factory export, evaluation |
| `brain/calendars/` | Shadow and Outlook calendars, description format |
| `listener/src/index.js` | Listener, catch-up after downtime |
| `listener/src/pickChats.js` | Chat picker |
| `listener/src/filters.js` | Which messages to forward, payload format |
| `listener/src/bridge.js` | HTTP sender with retry queue |
