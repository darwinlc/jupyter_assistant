"""
handlers.py  –  Tornado request handlers for ai_jupyter_server

Endpoints
─────────
POST /ai/complete   body: {content, file_type}          → {result}
POST /ai/edit       body: {content, instruction, file_type} → {result}
POST /ai/review     body: {content, file_type}          → {result}
POST /ai/ask        body: {question, file_type}         → {result}
GET  /ai/ping                                           → {status: "ok"}
"""

import json
import os
from openai import OpenAI
from jupyter_server.base.handlers import JupyterHandler
from tornado import web

# ── OpenAI client (lazy-initialised on first request) ───────────────────────
_client: OpenAI | None = None
_model       = os.environ.get("AI_JUPYTER_MODEL", "gpt-4o")
_temperature = float(os.environ.get("AI_JUPYTER_TEMP", "0.2"))
_max_tokens  = int(os.environ.get("AI_JUPYTER_MAX_TOKENS", "2048"))


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY environment variable is not set. "
                "Export it before starting JupyterLab."
            )
        _client = OpenAI(api_key=api_key)
    return _client


def _call(system: str, user: str) -> str:
    resp = _get_client().chat.completions.create(
        model=_model,
        temperature=_temperature,
        max_tokens=_max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    )
    return resp.choices[0].message.content.strip()


def _strip_fences(text: str) -> str:
    """Remove markdown code fences the model may have added."""
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines)


# ── File-type context helpers ────────────────────────────────────────────────

# Maps file extensions → human-readable language label used in prompts.
_LANG_MAP = {
    # Code
    "py"   : "Python",
    "js"   : "JavaScript",
    "ts"   : "TypeScript",
    "jsx"  : "React JSX",
    "tsx"  : "React TSX",
    "java" : "Java",
    "cpp"  : "C++",
    "c"    : "C",
    "cs"   : "C#",
    "go"   : "Go",
    "rs"   : "Rust",
    "rb"   : "Ruby",
    "php"  : "PHP",
    "swift": "Swift",
    "kt"   : "Kotlin",
    "r"    : "R",
    "scala": "Scala",
    "lua"  : "Lua",
    # Data / config
    "sql"  : "SQL",
    "sh"   : "Shell / Bash",
    "bash" : "Shell / Bash",
    "zsh"  : "Shell / Zsh",
    "ps1"  : "PowerShell",
    "yaml" : "YAML",
    "yml"  : "YAML",
    "toml" : "TOML",
    "json" : "JSON",
    "xml"  : "XML",
    "html" : "HTML",
    "css"  : "CSS",
    "scss" : "SCSS",
    # Prose / docs
    "md"   : "Markdown",
    "rst"  : "reStructuredText",
    "tex"  : "LaTeX",
    "txt"  : "plain text",
    # Notebooks
    "ipynb": "Jupyter Notebook (Python)",
}

# Extra context injected into prompts per language group.
_LANG_HINTS = {
    "Python"              : "Follow PEP 8. Add type hints and docstrings where suitable.",
    "JavaScript"          : "Use modern ES2020+ syntax. Prefer const/let, arrow functions.",
    "TypeScript"          : "Preserve all type annotations. Add missing types where obvious.",
    "SQL"                 : "Use ANSI SQL unless dialect hints suggest otherwise. Format with uppercase keywords.",
    "Shell / Bash"        : "Write POSIX-compatible shell unless bash-specific features are required.",
    "YAML"                : "Preserve indentation exactly. Return valid YAML.",
    "JSON"                : "Return valid, well-formatted JSON. No trailing commas.",
    "Markdown"            : "Preserve heading hierarchy. Keep prose concise and well-structured.",
    "reStructuredText"    : "Preserve RST directives and indentation exactly.",
    "LaTeX"               : "Preserve all LaTeX commands and environments.",
    "plain text"          : "Preserve the tone, style, and formatting of the original.",
}

_DEFAULT_HINT = "Preserve the structure, style, and formatting of the original."


def _lang_label(file_type: str) -> str:
    ext = (file_type or "").lower().lstrip(".")
    return _LANG_MAP.get(ext, f"{ext.upper()} file" if ext else "text")


def _lang_hint(label: str) -> str:
    return _LANG_HINTS.get(label, _DEFAULT_HINT)


# ── System prompt builders ───────────────────────────────────────────────────

def _complete_system(lang: str, hint: str) -> str:
    return f"""You are an expert {lang} assistant embedded in JupyterLab.
The user provides incomplete or stub content and you must complete it.

Rules:
- Return ONLY the completed {lang} content — no explanation, no markdown fences.
- Preserve the user's variable names, style, and indentation exactly.
- {hint}
- Replace stub markers (TODO, FIXME, pass, …, placeholder) with real, working content.
- If the content is prose (Markdown, plain text, RST), complete it naturally in the same voice."""


def _edit_system(lang: str, hint: str) -> str:
    return f"""You are an expert {lang} assistant performing a precise, targeted edit in JupyterLab.

Rules:
- Apply ONLY the change described in the instruction — nothing more.
- Return ONLY the edited {lang} content — no explanation, no markdown fences.
- {hint}
- Do not reformat or restructure anything the instruction did not mention."""


def _review_system(lang: str, hint: str) -> str:
    is_prose = lang in {"Markdown", "plain text", "reStructuredText", "LaTeX"}
    if is_prose:
        return f"""You are an expert {lang} editor reviewing a document in JupyterLab.
Return a structured review with these sections:
1. ✍️  Clarity & readability
2. 🏗  Structure & flow
3. 🔤  Grammar & style
4. 💡  Suggestions for improvement
5. ✅  Overall verdict

Be concise but specific. Use bullet points. Write "None" if a section has no issues."""
    else:
        return f"""You are a meticulous {lang} code reviewer embedded in JupyterLab.
Return a structured review with these sections:
1. 🐛  Bugs / Correctness
2. ⚡  Performance
3. 🔒  Security
4. 📖  Readability & style ({hint})
5. ✅  Summary & verdict

Be concise but specific. Use bullet points. Write "None" if a section has no issues."""


def _ask_system(lang: str) -> str:
    return f"""You are a helpful {lang} assistant embedded in JupyterLab.
Answer questions clearly and concisely. Use short code snippets where helpful.
Format your response with Markdown."""


# ── Base handler ─────────────────────────────────────────────────────────────

class _BaseHandler(JupyterHandler):
    """Shared JSON parsing / error response logic."""

    def set_default_headers(self):
        self.set_header("Content-Type", "application/json")
        # Allow requests from the JupyterLab frontend (same origin in practice)
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.set_header("Access-Control-Allow-Headers", "Content-Type")

    def options(self):
        self.set_status(204)
        self.finish()

    def json_body(self) -> dict:
        try:
            return json.loads(self.request.body)
        except Exception:
            raise web.HTTPError(400, "Invalid JSON body")

    def success(self, result: str):
        self.finish(json.dumps({"result": result}))

    def error(self, msg: str, code: int = 500):
        self.set_status(code)
        self.finish(json.dumps({"error": msg}))


# ── /ai/ping ─────────────────────────────────────────────────────────────────

class PingHandler(_BaseHandler):
    @web.authenticated
    def get(self):
        self.finish(json.dumps({"status": "ok", "model": _model}))


# ── /ai/complete ─────────────────────────────────────────────────────────────

class CompleteHandler(_BaseHandler):
    @web.authenticated
    def post(self):
        body      = self.json_body()
        content   = body.get("content", "").strip()
        file_type = body.get("file_type", "txt")

        if not content:
            return self.error("No content provided", 400)

        lang   = _lang_label(file_type)
        hint   = _lang_hint(lang)
        system = _complete_system(lang, hint)

        try:
            result = _call(system, content)
            self.success(_strip_fences(result))
        except Exception as e:
            self.error(str(e))


# ── /ai/edit ─────────────────────────────────────────────────────────────────

class EditHandler(_BaseHandler):
    @web.authenticated
    def post(self):
        body        = self.json_body()
        content     = body.get("content", "").strip()
        instruction = body.get("instruction", "").strip()
        file_type   = body.get("file_type", "txt")

        if not content:
            return self.error("No content provided", 400)
        if not instruction:
            return self.error("No instruction provided", 400)

        lang   = _lang_label(file_type)
        hint   = _lang_hint(lang)
        system = _edit_system(lang, hint)
        prompt = f"Instruction: {instruction}\n\nContent to edit:\n{content}"

        try:
            result = _call(system, prompt)
            self.success(_strip_fences(result))
        except Exception as e:
            self.error(str(e))


# ── /ai/review ───────────────────────────────────────────────────────────────

class ReviewHandler(_BaseHandler):
    @web.authenticated
    def post(self):
        body      = self.json_body()
        content   = body.get("content", "").strip()
        file_type = body.get("file_type", "txt")

        if not content:
            return self.error("No content provided", 400)

        lang   = _lang_label(file_type)
        hint   = _lang_hint(lang)
        system = _review_system(lang, hint)

        try:
            result = _call(system, content)
            self.success(result)   # keep Markdown formatting for review
        except Exception as e:
            self.error(str(e))


# ── /ai/ask ──────────────────────────────────────────────────────────────────

class AskHandler(_BaseHandler):
    @web.authenticated
    def post(self):
        body      = self.json_body()
        question  = body.get("question", "").strip()
        file_type = body.get("file_type", "txt")

        if not question:
            return self.error("No question provided", 400)

        lang   = _lang_label(file_type)
        system = _ask_system(lang)

        try:
            result = _call(system, question)
            self.success(result)
        except Exception as e:
            self.error(str(e))


# ── Route registration ────────────────────────────────────────────────────────

def setup_handlers(web_app):
    base = web_app.settings.get("base_url", "/")
    handlers = [
        (rf"{base}ai/ping",     PingHandler),
        (rf"{base}ai/complete", CompleteHandler),
        (rf"{base}ai/edit",     EditHandler),
        (rf"{base}ai/review",   ReviewHandler),
        (rf"{base}ai/ask",      AskHandler),
    ]
    web_app.add_handlers(".*", handlers)
