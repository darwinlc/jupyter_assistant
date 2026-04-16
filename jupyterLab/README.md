# 🤖 AI Jupyter Server Extension

AI-powered completion, editing, review, and Q&A for **any file type** in JupyterLab — `.py`, `.md`, `.sql`, `.yaml`, `.sh`, `.txt`, `.ipynb`, and more.

No npm. No build step. Pure Python + one JS file.

---

## How it works

```
Hotkey in JupyterLab (any file)
        │
        ▼
custom.js reads the active editor content + detects file type
        │
        ▼
POST /ai/complete  (or /edit, /review, /ask)
        │
        ▼
handlers.py  →  OpenAI API  (file-type-aware prompt)
        │
        ▼
Result written back into the editor at cursor / selection
```

---

## Requirements

```bash
pip install jupyter_server openai
```

Python 3.10+, JupyterLab 4.x.

---

## Installation

### Step 1 — Set your API key

```bash
export OPENAI_API_KEY="sk-..."
# Add to ~/.bashrc or ~/.zshrc to persist across sessions
```

### Step 2 — Install the Python package

```bash
cd ai_jupyter_server/
pip install -e .
```

### Step 3 — Enable the server extension

```bash
jupyter server extension enable ai_jupyter_server
```

Verify it registered correctly:

```bash
jupyter server extension list
# Should show: ai_jupyter_server  enabled
```

### Step 4 — Install the frontend hotkeys

```bash
# Create the custom JS directory if it doesn't exist
mkdir -p ~/.jupyter/custom

# Copy custom.js there
cp custom.js ~/.jupyter/custom/custom.js
```

### Step 5 — Restart JupyterLab

```bash
jupyter lab
```

Open any file. The hotkeys are now active.

---

## Hotkeys

| Shortcut | Action |
|---|---|
| `Ctrl+Shift+Space` | Complete — fills in stubs, finishes incomplete content |
| `Ctrl+Shift+E` | Edit — prompts for an instruction, then applies it |
| `Ctrl+Shift+V` | Review — structured analysis shown in a side panel |
| `Ctrl+Shift+A` | Ask — prompts for a question, answer shown in a side panel |

### Using selection

All actions respect text selection:
- **Text selected** → action applies to the selection only, result replaces the selection
- **Nothing selected** → action applies to the entire file, result replaces the whole file

---

## Supported file types

The extension auto-detects the file type and adjusts its prompts accordingly.

| Extension | Language | Prompt style |
|---|---|---|
| `.py` | Python | PEP 8, type hints, docstrings |
| `.js` / `.ts` | JavaScript / TypeScript | ES2020+, type preservation |
| `.sql` | SQL | ANSI SQL, uppercase keywords |
| `.sh` / `.bash` | Shell | POSIX-compatible |
| `.yaml` / `.yml` | YAML | Strict indentation, valid output |
| `.json` | JSON | Valid JSON, no trailing commas |
| `.md` | Markdown | Prose style, heading hierarchy |
| `.rst` | reStructuredText | Directive-aware |
| `.tex` | LaTeX | Environment-aware |
| `.txt` | Plain text | Tone and style matching |
| `.ipynb` | Jupyter Notebook | Python, notebook-aware |
| `.r` | R | R idioms |
| `.go`, `.rs`, `.java`, … | Other languages | Language-appropriate rules |

---

## Configuration

The server extension reads these environment variables at startup:

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | Your OpenAI API key |
| `AI_JUPYTER_MODEL` | `gpt-4o` | Model to use |
| `AI_JUPYTER_TEMP` | `0.2` | Temperature (0.0–1.0) |
| `AI_JUPYTER_MAX_TOKENS` | `2048` | Max tokens per response |

```bash
# Example: use a faster, cheaper model
export AI_JUPYTER_MODEL="gpt-4o-mini"
jupyter lab
```

---

## Remapping hotkeys

Edit the `HOTKEYS` object near the top of `~/.jupyter/custom/custom.js`:

```javascript
const HOTKEYS = {
  complete : { ctrl: true, shift: true, alt: false, key: " " },  // Ctrl+Shift+Space
  edit     : { ctrl: true, shift: true, alt: false, key: "e" },  // Ctrl+Shift+E
  review   : { ctrl: true, shift: true, alt: false, key: "v" },  // Ctrl+Shift+V
  ask      : { ctrl: true, shift: true, alt: false, key: "a" },  // Ctrl+Shift+A
};
```

Save the file and reload the browser tab — no restart needed.

---

## Using alongside the notebook magic extension

The server extension and the notebook magic (`ai_jupyter.py`) are fully independent and can run together:

| | Magic extension (`ai_jupyter.py`) | Server extension |
|---|---|---|
| Works in `.ipynb` | ✅ | ✅ |
| Works in `.py`, `.md`, `.sql` … | ❌ | ✅ |
| Requires kernel | Yes | No |
| Output location | Cell output area | In-editor (replaces text) |
| Hotkeys | Via kernel execute | Via `custom.js` direct fetch |

---

## File structure

```
ai_jupyter_server/
├── ai_jupyter_server/
│   ├── __init__.py          ← extension entry point
│   └── handlers.py          ← REST API + OpenAI logic + prompts
├── jupyter_server_config.d/
│   └── ai_jupyter_server.json  ← auto-enable config
├── setup.py                 ← pip install -e .
└── custom.js                ← copy to ~/.jupyter/custom/
```

---

## REST API

The extension exposes these endpoints (all require Jupyter authentication):

| Method | Path | Body | Response |
|---|---|---|---|
| `GET` | `/ai/ping` | — | `{status, model}` |
| `POST` | `/ai/complete` | `{content, file_type}` | `{result}` |
| `POST` | `/ai/edit` | `{content, instruction, file_type}` | `{result}` |
| `POST` | `/ai/review` | `{content, file_type}` | `{result}` |
| `POST` | `/ai/ask` | `{question, file_type}` | `{result}` |

You can call these from a notebook cell too:

```python
import requests, os

resp = requests.post(
    "http://localhost:8888/ai/complete",
    json={"content": "SELECT * FROM orders WHERE", "file_type": "sql"},
    headers={"X-XSRFToken": "..."}   # get from browser cookies
)
print(resp.json()["result"])
```

---

## Troubleshooting

**Extension not showing in `jupyter server extension list`**
→ Make sure you ran `pip install -e .` from inside the `ai_jupyter_server/` folder, then re-run `jupyter server extension enable ai_jupyter_server`.

**Hotkeys not working**
→ Confirm `custom.js` is at `~/.jupyter/custom/custom.js`. Hard-reload the browser (Ctrl+Shift+R). Check the browser console for the startup ping message.

**`OPENAI_API_KEY is not set` error**
→ The key must be exported in the same shell that runs `jupyter lab`. Add `export OPENAI_API_KEY="sk-..."` to your shell profile.

**Result replaces the whole file when I only wanted to edit a selection**
→ Make sure text is selected (highlighted) before pressing the hotkey. If nothing is selected, the action always targets the full file.

**`401 Unauthorized` from the API**
→ JupyterLab requires the XSRF token on POST requests. `custom.js` reads it automatically from cookies. If you see 401, check that you're accessing JupyterLab over the same origin (not a proxy that strips cookies).
