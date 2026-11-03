# Security

## Reporting a problem

Please **don't** open a public issue for security problems. Use GitHub's **Security → Report a vulnerability** (private advisory) on this repository. You'll get a reply within a week.

Relevant problems include anything that lets the bot:
- read chats that weren't selected
- send WhatsApp messages
- edit or delete calendar events it didn't create
- leak messages, tokens or the dataset off the laptop

## Secrets

These must never be committed: `.env`, `data/` (databases, `ms_token_cache.json`), `listener/.wwebjs_auth/`, `config/selected_chats.json`. All are in `.gitignore`, and CI runs gitleaks on every push.

If a token was committed by mistake: delete `data/ms_token_cache.json`, revoke the app's access at https://account.live.com/consent/Manage, and remove the file from git history.

## Supported versions

Only the latest release gets fixes.

See also [docs/PRIVACY.md](docs/PRIVACY.md).
