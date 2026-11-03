# Changelog

All notable changes to this project are listed here. The format follows [Keep a Changelog](https://keepachangelog.com) and versions follow [semantic versioning](https://semver.org).

## [Unreleased]

## [0.1.0] - 2026-11-04
### Added
- Read-only WhatsApp listener (whatsapp-web.js) with chat picker and catch-up after downtime
- Python brain: FastAPI bridge, Ollama decisions with JSON schema, date/time resolution in code (Hinglish words included)
- Shadow calendar (local SQLite) and Outlook calendar (Microsoft Graph, personal accounts, device-code sign-in)
- Calendar description used as the bot's long-term memory
- 2-day short-term memory with hourly cleanup, and a permanent dataset with a fixed train/test split
- Label Studio export/import, LLaMA-Factory export, `evaluate` command
- Tests (pytest, node:test), CI, Dependabot, docs
