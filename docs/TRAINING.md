# Dataset, labeling and training

Every message the model sees is stored in `data/dataset.db` with:

- the exact prompt the model got (message + 2-day context + calendar events)
- the model's raw answer and parsed decision
- what the bot actually did (created / updated / deleted / skipped, and why)
- a fixed **train/test split** (about 80/20, based on the message id, so a message never switches sides)
- your label, once you add one

`python -m brain stats` shows how many records you have and how many are labeled.

## 1. Collect (shadow mode)

Run with `MODE=shadow` for a few days. Check what it would have done with `python -m brain events --past 7`.

## 2. Label in Label Studio

```powershell
pip install label-studio      # in a separate venv is cleaner, it pulls in a lot
label-studio start
```

1. Create a project and paste the contents of `training/labelstudio_config.xml` under **Settings → Labeling Interface → Code**.
2. Export tasks from the bot: `python -m brain export-labelstudio` writes `data/exports/labelstudio_tasks.json`.
3. In Label Studio, choose **Import** and pick that file. Each task is pre-filled with the model's answer, so you only fix what's wrong and press **Submit**.
4. Label rules (consistency matters more than anything):
   - `date_text` / `time_text`: copy the words exactly as written in the message. Never write a computed date.
   - `target`: the number of the matching event in the "Events the bot already had" box, or 0.
   - Reminders of an event that already exists ("practice at 6 today, don't forget") are `none`, unless the calendar box is empty. In that case they're `add`.
5. **Export → JSON**, then: `python -m brain import-labelstudio path\to\export.json`

The import marks each record **correct** (you changed nothing) or **corrected**. The share of *correct* labels is a rough accuracy score for the current model.

## 3. Export for LLaMA-Factory

```powershell
python -m brain export-llamafactory
```

This writes `data/exports/llamafactory/` with `calbot_train.json`, `calbot_test.json` and `dataset_info.json` in LLaMA-Factory's *alpaca* format (columns `instruction`, `input`, `output`, `system`). The `system` field always holds the **current** system prompt, so training matches what the bot will use.

Rough guide: 200+ labeled examples before the first fine-tune, with a fair number of each action. You'll have far more `none` than anything else, so check the counts with `stats`.

## 4. Fine-tune

We'll set up LLaMA-Factory together when we get here. The plan:

- Base model: `Qwen/Qwen3-4B-Instruct-2507` (the same model as `calbot-base`)
- Method: LoRA / QLoRA (4-bit), which fits in the RTX 5050's 8 GB
- Train on `calbot_train`, keep `calbot_test` for evaluation only
- Export the merged model to GGUF, then `ollama create calbot-v1 -f Modelfile`

## 5. Evaluate before switching

```powershell
python -m brain evaluate --model calbot-base
python -m brain evaluate --model calbot-v1
```

This runs both models on the labeled **test** examples (never used in training) and reports per-field accuracy (`action`, `event`, `date_text`, `time_text`, `place`, `target`), the share with every field correct, and a few sample mistakes.

Switch only when the new model is clearly better, especially on `action` and `target`, the two fields that decide whether the bot edits the wrong event. Then set `OLLAMA_MODEL=calbot-v1` in `.env`.

## Changing the prompt

If you edit `SYSTEM_PROMPT` in `brain/prompts.py`, bump `PROMPT_VERSION`. Old records keep the version they were made with, so you can tell them apart.
