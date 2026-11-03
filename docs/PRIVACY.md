# Privacy and data

This bot reads private group chats, so here is exactly what it touches.

## What leaves the laptop

| Data | Goes to | When |
|---|---|---|
| Event title, time, place, and a description containing the source message | Your Outlook calendar (Microsoft) | Only in `MODE=live` |
| WhatsApp traffic | WhatsApp's servers, same as WhatsApp Web | Always |

Nothing goes to an online AI service. The model runs in Ollama on the laptop.

## What stays on the laptop

| File | Contains | Lifetime |
|---|---|---|
| `data/memory.db` | Messages from selected chats | Deleted after `MEMORY_DAYS` (2) |
| `data/dataset.db` | Messages the model looked at, plus context and decisions | Until you delete it |
| `data/shadow_calendar.db` | Shadow-mode events | Until you delete it |
| `data/ms_token_cache.json` | Outlook sign-in token | Until you delete it, which signs you out |
| `listener/.wwebjs_auth/` | WhatsApp Web login | Until you delete it, which logs out |
| `config/selected_chats.json` | Names and ids of chats you selected | Until you change it |

All of these are in `.gitignore`. **Never** commit them, upload them, or share the dataset publicly. It contains other people's messages.

## What the bot can and can't do

- It **can** read only the chats you selected, and create, edit or delete only calendar events that it created itself.
- It **can't** send WhatsApp messages, read unselected chats, or touch events you made yourself.

## Deleting everything

Stop both processes, then delete the `data/` folder contents, `listener/.wwebjs_auth/` and `config/selected_chats.json`. Then remove the linked device on your phone: WhatsApp → Settings → Linked devices.
