# GitHub repository metadata

Set these when you create the repo (Settings → General, and the ⚙ next to *About*).

**Description** (under 350 characters):

> Local AI bot that reads selected WhatsApp groups and automatically adds, reschedules and cancels events in your Outlook calendar. Runs fully on your laptop with Ollama, logs every decision as training data, and includes a Label Studio + LLaMA-Factory fine-tuning workflow.

**Topics:**

`whatsapp` `whatsapp-web-js` `outlook-calendar` `microsoft-graph` `ollama` `local-llm` `qwen3` `fine-tuning` `llama-factory` `label-studio` `fastapi` `calendar-automation` `python` `nodejs`

**Settings worth turning on:**
- Settings → Code security → **Secret scanning** and **Push protection**
- Settings → Code security → **Dependabot alerts**
- Settings → Branches → protect `main` (require the CI check to pass)

**CI badge** (after the first push, replace `USER/REPO`):

```markdown
![CI](https://github.com/USER/REPO/actions/workflows/ci.yml/badge.svg)
```
