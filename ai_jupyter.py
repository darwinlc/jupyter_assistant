"""
ai_jupyter.py  –  AI-powered code completion & editing for Jupyter Notebooks
Requires: pip install openai

Usage (in any notebook cell):
    %load_ext ai_jupyter          # load once per session
    %ai_setup                     # configure API key interactively

Completion magic  (%ai_complete):
    %%ai_complete
    def fibonacci(n):
        # complete this function
        pass

Edit magic  (%%ai_edit):
    %%ai_edit make this PEP-8 compliant and add type hints
    def add(x,y):
        return x+y

Inline helper  (%ai_ask):
    %ai_ask How do I read a CSV with pandas and parse dates?
"""

from IPython.core.magic import register_line_magic, register_cell_magic, register_line_cell_magic
from IPython.core.magic_arguments import magic_arguments, argument, parse_argstring
from IPython.display import display, Markdown, HTML
from openai import OpenAI
import os, textwrap, time, sys

# ── Module-level state ───────────────────────────────────────────────────────
_client: OpenAI | None = None
_model   = "gpt-4o"
_config  = {
    "temperature"     : 0.2,
    "max_tokens"      : 2048,
    "show_cost_hint"  : True,
}

# ── Pretty display helpers ───────────────────────────────────────────────────
_CSS = """
<style>
.ai-box {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    border-left: 3px solid #7c6af7;
    background: #0f0f1a;
    color: #e0deff;
    padding: 12px 16px;
    border-radius: 0 8px 8px 0;
    margin: 8px 0;
    white-space: pre-wrap;
    font-size: 13px;
    line-height: 1.6;
}
.ai-label {
    font-size: 10px;
    color: #7c6af7;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin-bottom: 6px;
}
.ai-info  { border-left-color: #22d3ee; color: #cffafe; background: #0a1628; }
.ai-error { border-left-color: #f87171; color: #fee2e2; background: #1a0a0a; }
.ai-ok    { border-left-color: #4ade80; color: #dcfce7; background: #0a1a0a; }
</style>
"""

def _show(content: str, kind: str = "", label: str = "AI OUTPUT"):
    display(HTML(_CSS + f'<div class="ai-box {kind}"><div class="ai-label">{label}</div>{content}</div>'))

def _err(msg: str):
    _show(msg, "ai-error", "ERROR")

def _ok(msg: str):
    _show(msg, "ai-ok", "READY")

# ── Core API call ────────────────────────────────────────────────────────────
def _call(system: str, user: str) -> str:
    if _client is None:
        raise RuntimeError("Run %ai_setup or set OPENAI_API_KEY first.")
    resp = _client.chat.completions.create(
        model=_model,
        temperature=_config["temperature"],
        max_tokens=_config["max_tokens"],
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    )
    return resp.choices[0].message.content.strip()

def _extract_code(text: str) -> str:
    """Strip markdown fences if the model wrapped the code."""
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)

# ── Magic: %ai_setup ─────────────────────────────────────────────────────────
def ai_setup(line):
    """Configure the assistant.  Usage: %ai_setup [model] [api_key]"""
    global _client, _model
    parts = line.strip().split()

    # Try environment variable first
    api_key = os.environ.get("OPENAI_API_KEY", "")

    if len(parts) >= 1 and parts[0].startswith("gpt"):
        _model = parts[0]
        parts = parts[1:]

    if parts:
        api_key = parts[0]
    elif not api_key:
        import getpass
        api_key = getpass.getpass("🔑  OpenAI API key: ")

    _client = OpenAI(api_key=api_key)
    _ok(f"Assistant ready  |  model: <b>{_model}</b>  |  temp: {_config['temperature']}")

# ── Magic: %%ai_complete ─────────────────────────────────────────────────────
COMPLETE_SYS = """You are an expert Python developer embedded in a Jupyter notebook.
The user provides incomplete or stub code.  Complete it fully.
Rules:
- Return ONLY the completed Python code – no explanation, no markdown fences.
- Preserve the user's variable names, style, and indentation.
- Add concise docstrings and type hints where appropriate.
- If the stub already has comments like `# TODO` or `pass`, replace them with real code."""

def ai_complete(line, cell):
    """Complete the code in this cell using AI.
    Usage:
        %%ai_complete
        def my_func():
            pass
    """
    try:
        result = _call(COMPLETE_SYS, cell)
        code = _extract_code(result)
        _show(code, label="▶  COMPLETED CODE  (copy & paste above)")
    except Exception as e:
        _err(str(e))

# ── Magic: %%ai_edit ─────────────────────────────────────────────────────────
EDIT_SYS = """You are a senior Python engineer doing a precise code edit.
The user gives an instruction on the first line (after %%ai_edit), then the code to edit.
Rules:
- Apply ONLY the requested change.
- Return ONLY the edited Python code – no explanation, no markdown fences.
- Keep everything the user did not ask you to change.
- Preserve indentation and line endings."""

def ai_edit(line, cell):
    """Edit the code in this cell according to the instruction.
    Usage:
        %%ai_edit add type hints and make it PEP-8 compliant
        def add(x,y):
            return x+y
    """
    instruction = line.strip()
    if not instruction:
        _err("Provide an edit instruction after %%ai_edit, e.g.: %%ai_edit add error handling")
        return
    try:
        prompt = f"Instruction: {instruction}\n\nCode to edit:\n{cell}"
        result = _call(EDIT_SYS, prompt)
        code = _extract_code(result)
        _show(code, label=f"✏  EDITED  ({instruction})")
    except Exception as e:
        _err(str(e))

# ── Magic: %%ai_review ───────────────────────────────────────────────────────
REVIEW_SYS = """You are a meticulous Python code reviewer.
Analyse the provided code and return a structured review with these sections:
1. 🐛 Bugs / Correctness issues
2. ⚡ Performance
3. 🔒 Security
4. 📖 Readability & style
5. ✅ Summary & verdict

Be concise but specific.  Use bullet points.  If a section has no issues, write "None"."""

def ai_review(line, cell):
    """Review the code in this cell.
    Usage:
        %%ai_review
        <your code here>
    """
    try:
        result = _call(REVIEW_SYS, cell)
        display(Markdown(result))
    except Exception as e:
        _err(str(e))

# ── Magic: %ai_ask (line magic) ──────────────────────────────────────────────
ASK_SYS = """You are a helpful Python / data-science tutor embedded in Jupyter.
Answer the question concisely.  Use short code snippets where helpful.
Format with Markdown.  Assume Python 3.10+, pandas, numpy, matplotlib available."""

def ai_ask(line):
    """%ai_ask <question>   – Ask any Python / data-science question."""
    question = line.strip()
    if not question:
        _err("Usage: %ai_ask How do I pivot a DataFrame?")
        return
    try:
        result = _call(ASK_SYS, question)
        display(Markdown(result))
    except Exception as e:
        _err(str(e))

# ── Magic: %ai_config ────────────────────────────────────────────────────────
def ai_config(line):
    """%ai_config [key=value ...]   – Tune settings.
    Keys: model, temperature, max_tokens
    Example: %ai_config model=gpt-4o temperature=0.1
    """
    global _model
    if not line.strip():
        info = (f"model={_model}  temperature={_config['temperature']}  "
                f"max_tokens={_config['max_tokens']}")
        _show(info, "ai-info", "CONFIG")
        return
    for pair in line.strip().split():
        if "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        if k == "model":
            _model = v
        elif k == "temperature":
            _config["temperature"] = float(v)
        elif k == "max_tokens":
            _config["max_tokens"] = int(v)
    ai_config("")   # echo updated config

# ── Extension loader ─────────────────────────────────────────────────────────
def load_ipython_extension(ipython):
    ipython.register_magic_function(ai_setup,    magic_kind="line",      magic_name="ai_setup")
    ipython.register_magic_function(ai_complete, magic_kind="cell",      magic_name="ai_complete")
    ipython.register_magic_function(ai_edit,     magic_kind="cell",      magic_name="ai_edit")
    ipython.register_magic_function(ai_review,   magic_kind="cell",      magic_name="ai_review")
    ipython.register_magic_function(ai_ask,      magic_kind="line",      magic_name="ai_ask")
    ipython.register_magic_function(ai_config,   magic_kind="line",      magic_name="ai_config")

    display(HTML(_CSS + """
    <div class="ai-box ai-ok">
      <div class="ai-label">AI JUPYTER ASSISTANT  ·  LOADED</div>
      <b>%ai_setup</b>          → configure API key &amp; model<br>
      <b>%%ai_complete</b>      → complete stub / partial code<br>
      <b>%%ai_edit  &lt;instr&gt;</b> → apply a targeted code edit<br>
      <b>%%ai_review</b>        → get a structured code review<br>
      <b>%ai_ask  &lt;question&gt;</b> → ask any Python question<br>
      <b>%ai_config</b>         → view / change settings
    </div>"""))
