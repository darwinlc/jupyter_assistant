"""
ai_jupyter.py  –  AI-powered code completion & editing for Jupyter Notebooks
Requires: pip install openai

Usage (in any notebook cell):
    %load_ext ai_jupyter          # load once per session
    %ai_setup                     # configure API key interactively

Completion magic  (%%ai_complete  |  hotkey Ctrl+Shift+Space):
    %%ai_complete
    def fibonacci(n):
        # complete this function
        pass

Edit magic  (%%ai_edit  |  hotkey Ctrl+Shift+E then type instruction):
    %%ai_edit make this PEP-8 compliant and add type hints
    def add(x,y):
        return x+y

Inline replace  (hotkey Ctrl+Shift+R  – rewrites cell content in-place):
    Write code with # TODO / pass stubs, press Ctrl+Shift+R

Inline helper  (%ai_ask):
    %ai_ask How do I read a CSV with pandas and parse dates?

Default hotkeys (reconfigure with %ai_hotkeys):
    Ctrl+Shift+Space  →  complete current cell
    Ctrl+Shift+E      →  edit current cell  (prompts for instruction)
    Ctrl+Shift+R      →  complete & REPLACE cell content in-place
    Ctrl+Shift+V      →  review current cell
"""

from IPython.core.magic import register_line_magic, register_cell_magic, register_line_cell_magic
from IPython.core.magic_arguments import magic_arguments, argument, parse_argstring
from IPython.display import display, Markdown, HTML
from openai import OpenAI
import os, textwrap, time, sys, json

# ── Module-level state ───────────────────────────────────────────────────────
_client: OpenAI | None = None
_model   = "gpt-4o"
_config  = {
    "temperature"     : 0.2,
    "max_tokens"      : 2048,
    "show_cost_hint"  : True,
}

# ── Hotkey defaults (override with %ai_hotkeys) ──────────────────────────────
_hotkeys = {
    "complete" : "Ctrl-Shift-Space",   # show completion in output area
    "replace"  : "Ctrl-Shift-R",       # complete & replace cell in-place
    "edit"     : "Ctrl-Shift-E",       # prompt-then-edit
    "review"   : "Ctrl-Shift-V",       # code review
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

# ── Magic: %%ai_replace (complete & overwrite cell) ─────────────────────────
def ai_replace(line, cell):
    """Complete the code and REPLACE this cell's content in-place.
    The original stub is overwritten with the completed version.

    Works in classic Notebook only (requires Jupyter JS API).
    In JupyterLab use the %%ai_complete magic instead.
    """
    try:
        result = _call(COMPLETE_SYS, cell)
        code = _extract_code(result)
        # Inject JS to overwrite the currently selected cell
        escaped = json.dumps(code)
        js = f"""
        (function() {{
            var nb = Jupyter.notebook;
            if (!nb) {{ console.warn('ai_replace: classic Notebook not detected'); return; }}
            var cell = nb.get_selected_cell();
            cell.set_text({escaped});
            cell.render();
        }})();
        """
        display(HTML(f"<script>{js}</script>"))
        _ok("Cell replaced in-place ✓")
    except Exception as e:
        _err(str(e))


# ── Magic: %ai_hotkeys ───────────────────────────────────────────────────────
def ai_hotkeys(line):
    """%ai_hotkeys [action=KeyCombo ...]   – View or remap hotkeys, then re-inject JS.
    Example: %ai_hotkeys complete=Ctrl-Shift-K replace=Ctrl-Shift-R
    """
    if line.strip():
        for pair in line.strip().split():
            if "=" not in pair:
                continue
            k, v = pair.split("=", 1)
            if k in _hotkeys:
                _hotkeys[k] = v
    # Always re-inject JS with current bindings
    _inject_hotkeys()
    rows = "  ".join(f"<b>{v}</b> → {k}" for k, v in _hotkeys.items())
    _show(rows, "ai-info", "HOTKEYS")


# ── JavaScript hotkey injector ───────────────────────────────────────────────
# Strategy:
#   Classic Notebook  → uses Jupyter.keyboard_manager + CodeMirror extraKeys
#   JupyterLab        → dispatches a custom kernel execute via window._ai_lab_exec
#
# The JS reads the active cell, sends a kernel execute request with a special
# sentinel magic (%_ai_hotkey_trigger <action> <code_b64>), which the Python
# side intercepts and dispatches to the correct handler.

def _inject_hotkeys():
    """Inject / refresh keyboard shortcuts into the running notebook frontend."""
    hk = _hotkeys
    js = f"""
(function() {{
  // ── helpers ────────────────────────────────────────────────────────────────
  function b64(str) {{
    try {{ return btoa(unescape(encodeURIComponent(str))); }}
    catch(e) {{ return btoa(str); }}
  }}

  function runAction(action) {{
    var code = "";

    // ── Classic Notebook ────────────────────────────────────────────────────
    if (typeof Jupyter !== "undefined" && Jupyter.notebook) {{
      var cell = Jupyter.notebook.get_selected_cell();
      code = cell ? cell.get_text() : "";
      if (action === "edit") {{
        var instr = prompt("✏  Edit instruction:");
        if (!instr) return;
        Jupyter.notebook.kernel.execute(
          "%_ai_hotkey_trigger edit " + b64(instr) + " " + b64(code),
          {{ iopub: {{ output: function(msg) {{}} }} }}, {{ silent: false }}
        );
      }} else {{
        Jupyter.notebook.kernel.execute(
          "%_ai_hotkey_trigger " + action + " " + b64(code),
          {{ iopub: {{ output: function(msg) {{}} }} }}, {{ silent: false }}
        );
      }}
      return;
    }}

    // ── JupyterLab ──────────────────────────────────────────────────────────
    // JupyterLab exposes the active cell via the tracker; we reach it through
    // the global app shell (window.jupyterapp or window._jp_app set below).
    var app = window.jupyterapp || window._jp_app;
    if (app) {{
      try {{
        var tracker = app.shell.currentWidget;
        var activeCell = tracker && tracker.content && tracker.content.activeCell;
        code = activeCell ? activeCell.model.sharedModel.getSource() : "";
      }} catch(e) {{ code = ""; }}
      var instr = (action === "edit") ? prompt("✏  Edit instruction:") : null;
      if (action === "edit" && !instr) return;
      var kernelCommand = (action === "edit")
        ? "%_ai_hotkey_trigger edit " + b64(instr) + " " + b64(code)
        : "%_ai_hotkey_trigger " + action + " " + b64(code);
      // Execute via the session context
      try {{
        var session = tracker.sessionContext || tracker.content.sessionContext;
        session.session.kernel.requestExecute({{ code: kernelCommand }});
      }} catch(e) {{ console.warn("ai hotkey: lab exec failed", e); }}
      return;
    }}

    console.warn("AI Jupyter: no notebook runtime detected for hotkey");
  }}

  // ── Classic Notebook: register via keyboard_manager ─────────────────────
  if (typeof Jupyter !== "undefined" && Jupyter.keyboard_manager) {{
    var km = Jupyter.keyboard_manager;
    km.command_shortcuts.remove_shortcut("{hk['complete']}");
    km.command_shortcuts.remove_shortcut("{hk['replace']}");
    km.command_shortcuts.remove_shortcut("{hk['edit']}");
    km.command_shortcuts.remove_shortcut("{hk['review']}");

    function makeHandler(action) {{
      return {{ help: "AI: " + action, handler: function() {{ runAction(action); return false; }} }};
    }}
    km.command_shortcuts.add_shortcut("{hk['complete']}", makeHandler("complete"));
    km.command_shortcuts.add_shortcut("{hk['replace']}",  makeHandler("replace"));
    km.command_shortcuts.add_shortcut("{hk['edit']}",     makeHandler("edit"));
    km.command_shortcuts.add_shortcut("{hk['review']}",   makeHandler("review"));
    console.log("AI Jupyter: hotkeys registered (classic notebook)");
    return;
  }}

  // ── JupyterLab: register via document keydown (fallback) ─────────────────
  // Remove previous listener if re-injecting
  if (window._ai_jupyter_keydown) {{
    document.removeEventListener("keydown", window._ai_jupyter_keydown, true);
  }}

  function matchesHotkey(e, combo) {{
    // Parse "Ctrl-Shift-Space" style
    var parts = combo.split("-");
    var key   = parts[parts.length - 1].toLowerCase();
    var ctrl  = parts.includes("Ctrl");
    var shift = parts.includes("Shift");
    var alt   = parts.includes("Alt");
    var ekey  = e.key === " " ? "space" : e.key.toLowerCase();
    return e.ctrlKey === ctrl && e.shiftKey === shift && e.altKey === alt && ekey === key;
  }}

  window._ai_jupyter_keydown = function(e) {{
    if (matchesHotkey(e, "{hk['complete']}")) {{ e.preventDefault(); e.stopPropagation(); runAction("complete"); }}
    if (matchesHotkey(e, "{hk['replace']}"))  {{ e.preventDefault(); e.stopPropagation(); runAction("replace"); }}
    if (matchesHotkey(e, "{hk['edit']}"))     {{ e.preventDefault(); e.stopPropagation(); runAction("edit"); }}
    if (matchesHotkey(e, "{hk['review']}"))   {{ e.preventDefault(); e.stopPropagation(); runAction("review"); }}
  }};
  document.addEventListener("keydown", window._ai_jupyter_keydown, true);
  console.log("AI Jupyter: hotkeys registered (JupyterLab / keydown fallback)");
}})();
"""
    display(HTML(f"<script>{js}</script>"))


# ── Kernel-side hotkey trigger (called by JS via kernel.execute) ─────────────
def _ai_hotkey_trigger(line):
    """Internal: dispatched by the JS hotkey handler via kernel.execute.
    Format: %_ai_hotkey_trigger <action> <b64_arg1> [<b64_arg2>]
    """
    import base64
    parts = line.strip().split()
    if not parts:
        return
    action = parts[0]

    def _b64d(s):
        try:
            return base64.b64decode(s).decode("utf-8")
        except Exception:
            return s

    if action == "complete" and len(parts) >= 2:
        code = _b64d(parts[1])
        ai_complete("", code)
    elif action == "replace" and len(parts) >= 2:
        code = _b64d(parts[1])
        ai_replace("", code)
    elif action == "edit" and len(parts) >= 3:
        instr = _b64d(parts[1])
        code  = _b64d(parts[2])
        ai_edit(instr, code)
    elif action == "review" and len(parts) >= 2:
        code = _b64d(parts[1])
        ai_review("", code)
    else:
        _err(f"Unknown hotkey action: {action}")


# ── Extension loader ─────────────────────────────────────────────────────────
def load_ipython_extension(ipython):
    ipython.register_magic_function(ai_setup,             magic_kind="line", magic_name="ai_setup")
    ipython.register_magic_function(ai_complete,          magic_kind="cell", magic_name="ai_complete")
    ipython.register_magic_function(ai_edit,              magic_kind="cell", magic_name="ai_edit")
    ipython.register_magic_function(ai_review,            magic_kind="cell", magic_name="ai_review")
    ipython.register_magic_function(ai_replace,           magic_kind="cell", magic_name="ai_replace")
    ipython.register_magic_function(ai_ask,               magic_kind="line", magic_name="ai_ask")
    ipython.register_magic_function(ai_config,            magic_kind="line", magic_name="ai_config")
    ipython.register_magic_function(ai_hotkeys,           magic_kind="line", magic_name="ai_hotkeys")
    ipython.register_magic_function(_ai_hotkey_trigger,   magic_kind="line", magic_name="_ai_hotkey_trigger")

    # Inject JS hotkeys immediately
    _inject_hotkeys()

    display(HTML(_CSS + f"""
    <div class="ai-box ai-ok">
      <div class="ai-label">AI JUPYTER ASSISTANT  ·  LOADED</div>
      <b>%ai_setup</b>              → configure API key &amp; model<br>
      <b>%%ai_complete</b>          → show completion in output area<br>
      <b>%%ai_replace</b>           → complete &amp; overwrite cell in-place<br>
      <b>%%ai_edit  &lt;instr&gt;</b>   → apply a targeted code edit<br>
      <b>%%ai_review</b>            → get a structured code review<br>
      <b>%ai_ask  &lt;question&gt;</b>  → ask any Python question<br>
      <b>%ai_config</b>             → view / change model &amp; settings<br>
      <b>%ai_hotkeys</b>            → view / remap keyboard shortcuts<br>
      <br>
      <span style="color:#22d3ee">⌨  Default hotkeys</span><br>
      <b>{_hotkeys['complete']}</b>  complete (output below)<br>
      <b>{_hotkeys['replace']}</b>   complete &amp; replace cell in-place<br>
      <b>{_hotkeys['edit']}</b>      edit  (prompts for instruction)<br>
      <b>{_hotkeys['review']}</b>    review
    </div>"""))
