# 🤖 AI Jupyter Assistant

AI-powered code completion, editing, and review for Jupyter Notebooks — powered by OpenAI, zero plugins required.

---

## Requirements

```bash
pip install openai
```

Python 3.10+ and any Jupyter environment (classic Notebook, JupyterLab, VS Code, Google Colab).

---

## Installation

Choose one option. You only need to do this once.

### Option A — Quickest: copy to site-packages

```bash
# Find your site-packages folder
python -c "import site; print(site.getusersitepackages())"

# Copy the file there (adjust path to match output above)
cp ai_jupyter.py ~/.local/lib/python3.11/site-packages/
```

### Option B — Cleanest: install as a package

```bash
# In the folder containing ai_jupyter.py
pip install -e .
```

### Option C — No file move: add folder to IPython startup

Create the file `~/.ipython/profile_default/startup/00_ai_path.py`:

```python
import sys
sys.path.insert(0, "/absolute/path/to/folder/containing/ai_jupyter")
```

This runs automatically every time Jupyter starts.

> **Note:** `ai_jupyter.py` does **not** need to be in the same folder as your notebooks.

---

## Quick Start

Add these two cells at the top of any notebook:

```python
# Cell 1 — load once per session
%load_ext ai_jupyter
```

```python
# Cell 2 — configure (reads OPENAI_API_KEY env var, or prompts you)
%ai_setup
```

To avoid being prompted every session, set your key as an environment variable:

```bash
export OPENAI_API_KEY="sk-..."   # add to ~/.bashrc or ~/.zshrc to persist
```

---

## Commands

### `%%ai_complete` — Complete stub code

Fills in incomplete functions, replaces `pass` / `# TODO`, adds docstrings and type hints.

```python
%%ai_complete
def fibonacci(n: int):
    # return the nth Fibonacci number using memoisation
    pass
```

The completed code is shown **below the cell** for you to review before using.

---

### `%%ai_replace` — Complete & overwrite in-place

Same as `%%ai_complete` but **replaces the cell content** directly. Best for classic Notebook.

```python
%%ai_replace
def fibonacci(n: int):
    pass
```

> ⚠️ This rewrites your cell. Use `%%ai_complete` if you want to review first.

---

### `%%ai_edit <instruction>` — Targeted code edit

Apply a specific change to existing code. The instruction goes on the same line as the magic.

```python
%%ai_edit add type hints, a docstring, and proper error handling
def divide(a, b):
    return a / b
```

```python
%%ai_edit convert the loop to a list comprehension
def square_evens(numbers):
    result = []
    for n in numbers:
        if n % 2 == 0:
            result.append(n ** 2)
    return result
```

---

### `%%ai_review` — Structured code review

Analyses your code across five dimensions: bugs, performance, security, readability, and an overall verdict.

```python
%%ai_review
import sqlite3

def get_user(username):
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM users WHERE name = '{username}'")
    return cur.fetchall()
```

---

### `%ai_ask <question>` — Quick Q&A

Ask any Python or data-science question. Assumes pandas, numpy, and matplotlib are available.

```python
%ai_ask How do I merge two DataFrames on multiple keys keeping only matching rows?
```

```python
%ai_ask What is the difference between __repr__ and __str__?
```

---

## Keyboard Shortcuts

Hotkeys are injected automatically when the extension loads. Press a shortcut while a cell is selected:

| Shortcut | Action |
|---|---|
| `Ctrl+Shift+Space` | Complete current cell (output shown below) |
| `Ctrl+Shift+R` | Complete & replace cell content in-place |
| `Ctrl+Shift+E` | Edit current cell (browser prompts for instruction) |
| `Ctrl+Shift+V` | Review current cell |

### Remapping hotkeys

```python
# View current bindings
%ai_hotkeys

# Remap one or more keys
%ai_hotkeys complete=Ctrl-Shift-K edit=Ctrl-Shift-I replace=Ctrl-Alt-R
```

Key combo format: `Ctrl`, `Shift`, `Alt` joined by `-`, then the key — e.g. `Ctrl-Shift-Space`, `Ctrl-Alt-R`.

> **JupyterLab note:** Hotkeys use a `keydown` event listener (injected via cell output). They work in JupyterLab but are slightly less native than in classic Notebook.

---

## Configuration

```python
# View current settings
%ai_config

# Change model (useful to switch between speed and quality)
%ai_config model=gpt-4o-mini          # faster, cheaper

# Tune creativity (0.0 = deterministic, 1.0 = creative)
%ai_config temperature=0.0

# Allow longer completions
%ai_config max_tokens=4096
```

### Recommended models

| Model | Best for |
|---|---|
| `gpt-4o` *(default)* | Complex completions, tricky refactors |
| `gpt-4o-mini` | Quick edits, simple questions |

---

## Using alongside your own OpenAI client

The extension stores its client in its own module scope (`ai_jupyter._client`). It **does not interfere** with any `OpenAI` client you create in your notebook.

```python
# Your notebook code — completely independent
from openai import OpenAI
client = OpenAI(api_key="sk-...")
client.chat.completions.create(...)   # uses YOUR client

# Extension uses ai_jupyter._client internally — no overlap
```

**Optional:** share your existing client with the extension to avoid duplicating your API key:

```python
import ai_jupyter
ai_jupyter._client = client       # reuse your client
ai_jupyter._model  = "gpt-4o"    # optionally sync the model
```

---

## Command Reference

| Command | Kind | Description |
|---|---|---|
| `%ai_setup [model] [key]` | line | Configure API key and model |
| `%%ai_complete` | cell | Complete stub code, show in output |
| `%%ai_replace` | cell | Complete stub code, overwrite cell |
| `%%ai_edit <instruction>` | cell | Apply a targeted edit |
| `%%ai_review` | cell | Structured code review |
| `%ai_ask <question>` | line | Quick Python / data-science Q&A |
| `%ai_config [key=value]` | line | View or change settings |
| `%ai_hotkeys [action=combo]` | line | View or remap keyboard shortcuts |

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'ai_jupyter'`**
→ The file isn't on Python's path. Follow one of the three installation options above.

**`Run %ai_setup or set OPENAI_API_KEY first`**
→ You skipped setup. Run `%ai_setup` or set the `OPENAI_API_KEY` environment variable.

**Hotkeys don't work in JupyterLab**
→ Re-run `%ai_hotkeys` to re-inject the JS listener. This is needed if the output cell was cleared.

**`%%ai_replace` doesn't overwrite the cell**
→ `%%ai_replace` requires the classic Notebook JS API (`Jupyter.notebook`). In JupyterLab, use `%%ai_complete` and copy the result manually.

**Completion output contains markdown fences (` ```python `)**
→ The extension strips these automatically. If you still see them, the model returned an unexpected format — try re-running.
