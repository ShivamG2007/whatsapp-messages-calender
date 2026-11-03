# Setup

Written for Windows + PowerShell. Every command is run from the project folder unless it says otherwise.

## 1. Requirements

| Tool | Check | Notes |
|---|---|---|
| Python 3.11+ | `python --version` | |
| Node.js 20.12+ | `node -v` | |
| Git | `git --version` | |
| Ollama | `ollama --version` | https://ollama.com |
| NVIDIA driver | `nvidia-smi` | Optional, but the model is much faster on a GPU |

## 2. Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

If PowerShell says *running scripts is disabled*, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

You must see `(.venv)` at the start of the prompt whenever you work on the project.

## 3. The model

The bot uses the **Instruct** (non-thinking) version of Qwen3-4B. The thinking version writes pages of reasoning before every answer and takes about 60 s per message instead of about 1 s.

```powershell
ollama pull hf.co/unsloth/Qwen3-4B-Instruct-2507-GGUF:Q4_K_M
ollama cp hf.co/unsloth/Qwen3-4B-Instruct-2507-GGUF:Q4_K_M calbot-base
python -m brain check
```

`check` should say the model was found.

Test the full pipeline without WhatsApp:

```powershell
python -m brain try "dance practice kal 7 baje at OAT" --chat "Dance group"
python -m brain events
```

`try` writes to the shadow calendar but keeps its records in `data/try_dataset.db`, so test messages never mix with your real training data.

## 4. WhatsApp listener

```powershell
cd listener
npm install
npm approve-scripts puppeteer     # newer npm blocks Puppeteer's Chrome download without this
npx puppeteer browsers install chrome
npm run pick
```

`npm run pick` shows a QR code. On your phone, go to **WhatsApp → Settings → Linked devices → Link a device** and scan it. Then type the numbers of the chats the bot may read, e.g. `3,7,12`. The choice is saved to `config/selected_chats.json`. Run `npm run pick` again any time to change it. Stop the listener first, because only one WhatsApp session can use the login at a time.

The login is saved in `listener/.wwebjs_auth/`, so you only scan once. Delete that folder to log out.

## 5. Run

```powershell
# terminal 1 (project folder, (.venv) active)
python -m brain serve

# terminal 2
cd listener
npm start
```

Or open both at once: `powershell -ExecutionPolicy Bypass -File scripts\start.ps1`

When the listener starts, it catches up on messages from the last `BACKFILL_HOURS` hours (36 by default) that arrived while the laptop was off.

## 6. Outlook (needed only for live mode)

You need a free app registration so the bot is allowed to edit your calendar. This is a one-time setup.

1. Go to https://entra.microsoft.com (or https://portal.azure.com → *Microsoft Entra ID*) and sign in with your **personal** Microsoft account. If it asks you to create a free Azure account or directory, do that. It costs nothing.
2. **App registrations → New registration**
   - Name: `WhatsApp Calendar Bot` (anything)
   - Supported account types: **Personal Microsoft accounts only**
   - Redirect URI: leave empty
   - Click **Register**
3. Copy the **Application (client) ID** into `.env` as `MS_CLIENT_ID=...`
4. **Authentication** → *Advanced settings* → **Allow public client flows: Yes** → Save. The device-code sign-in needs this.
5. **API permissions → Add a permission → Microsoft Graph → Delegated** → tick **Calendars.ReadWrite** → Add.
6. Sign in once:
   ```powershell
   python -m brain login
   ```
   It prints a code and a link. Open the link, enter the code and approve. The token is saved to `data/ms_token_cache.json`, which is git-ignored. Never share it.
7. Set `MODE=live` in `.env`, then run `python -m brain check`.

Events created by the bot get the Outlook category **CalBot**, so you can colour them in Outlook.

## Troubleshooting

| Problem | Fix |
|---|---|
| Listener says *No chats selected* | `cd listener; npm run pick` |
| QR code keeps coming back / login fails | Close the listener, delete `listener/.wwebjs_auth`, run `npm run pick` again |
| Listener crashes right after WhatsApp updates | `cd listener; npm install whatsapp-web.js@latest` |
| Brain: *Failed to connect to Ollama* | Start the Ollama app, then `python -m brain check` |
| Listener: *Brain not reachable* | Start `python -m brain serve` first. Messages wait in a queue and are sent once it's up |
| Wrong date for "kal"/"7" | See the rules in `brain/dates.py`, and label the example so training fixes the model's side |
