# Roadmap

Versions follow [semantic versioning](https://semver.org): `MAJOR.MINOR.PATCH`. Changes are listed in [CHANGELOG.md](../CHANGELOG.md).

## 0.1 (now)
- Read-only listener for selected chats, with catch-up after downtime
- Local model decisions with dates resolved in code
- Shadow and Outlook calendars, with the calendar description as long-term memory
- 2-day memory and a permanent dataset
- Label Studio round trip, LLaMA-Factory export, evaluation

## 0.2: first fine-tuned model
- Collect and label 200+ examples
- LLaMA-Factory QLoRA config for Qwen3-4B-Instruct on an 8 GB GPU
- `calbot-v1` beats `calbot-base` on the test split
- Switch to live mode

## Later ideas
- Daily summary of what the bot changed
- Optional confirmation for low-confidence decisions
- Recurring events ("practice every Tue and Thu")
- Better handling of polls ("vote for practice time")
