from datetime import datetime

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = """You read WhatsApp messages from college club, sports and dance groups and decide if a calendar event must change.

Pick exactly one action:
- add: the message announces a NEW meeting, practice, match, class, session or deadline with a day or time.
- reschedule: the message changes the day, time or place of an event that already exists.
- cancel: the message says an existing event is cancelled or will not happen.
- none: anything else (questions, chit-chat, reminders that change nothing, past events, polls without a decision).

Rules:
- date_text and time_text: COPY the words from the message exactly ("tomorrow", "kal", "friday", "5 nov", "7pm", "shaam 6", "6-8pm"). Never calculate a date yourself. Use "" if the message does not say it.
- end_time_text: only if an end time is given separately, else "".
- event: a short title such as "Dance practice" or "LEAP club meeting". Use the group name if the message does not name the event.
- place: copy the place if given, else "".
- target: for reschedule or cancel, the number of the matching event from "Events already in the calendar". Use 0 if none match or for add/none.
- confidence: 0 to 1, how sure you are about the action.

Examples:
Message: "practice tomorrow 6pm at the court, be on time"
{"action":"add","event":"Practice","date_text":"tomorrow","time_text":"6pm","end_time_text":"","place":"court","target":0,"confidence":0.9}
Message: "guys meeting shifted to 7 instead of 5" (calendar has 1. LEAP meeting | Thu 17:00)
{"action":"reschedule","event":"LEAP meeting","date_text":"","time_text":"7","end_time_text":"","place":"","target":1,"confidence":0.85}
Message: "aaj ki practice cancel hai" (calendar has 1. Dance practice | today 18:00)
{"action":"cancel","event":"Dance practice","date_text":"aaj","time_text":"","end_time_text":"","place":"","target":1,"confidence":0.9}
Message: "who is coming for practice?"
{"action":"none","event":"","date_text":"","time_text":"","end_time_text":"","place":"","target":0,"confidence":0.8}

Reply with JSON only."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["add", "reschedule", "cancel", "none"]},
        "event": {"type": "string"},
        "date_text": {"type": "string"},
        "time_text": {"type": "string"},
        "end_time_text": {"type": "string"},
        "place": {"type": "string"},
        "target": {"type": "integer"},
        "confidence": {"type": "number"},
    },
    "required": ["action", "event", "date_text", "time_text", "end_time_text", "place", "target", "confidence"],
}


def format_context(rows, tz) -> str:
    lines = []
    for row in rows:
        when = datetime.fromtimestamp(row["ts"], tz).strftime("%a %H:%M")
        who = "me" if row["from_me"] else (row["sender"] or "someone")
        body = " ".join(row["body"].split())[:300]
        lines.append(f"[{when}] {who}: {body}")
    return "\n".join(lines) if lines else "(no earlier messages)"


def format_candidates(events) -> str:
    if not events:
        return "(none)"
    return "\n".join(f"{i}. {event.summary()}" for i, event in enumerate(events, start=1))


def build_user_prompt(chat_name: str, sender: str, body: str, sent_at: datetime, context_text: str, candidates_text: str) -> str:
    return (
        f"Group: {chat_name or 'unknown'}\n"
        f"Message sent at: {sent_at.strftime('%A %Y-%m-%d %H:%M')}\n\n"
        f"Earlier messages in this group (oldest first):\n{context_text}\n\n"
        f"Events already in the calendar:\n{candidates_text}\n\n"
        f'New message from {sender or "someone"}:\n"{body.strip()}"'
    )
