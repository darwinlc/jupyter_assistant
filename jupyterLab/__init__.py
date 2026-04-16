"""
ai_jupyter_server
─────────────────
JupyterLab server extension that adds AI-powered completion, edit, review,
and Q&A to ANY file type open in JupyterLab (Python, Markdown, SQL, YAML,
plain text, shell scripts, notebooks, …).

Entry point registered via setup.py / jupyter_server_config.py.
"""

from .handlers import setup_handlers          # noqa: F401


def _jupyter_server_extension_points():
    """
    Required by jupyter_server.  Returns the list of extension points
    this package provides.
    """
    return [{"module": "ai_jupyter_server"}]


def _load_jupyter_server_extension(server_app):
    """
    Called by jupyter_server when it loads this extension.
    Registers all HTTP handlers under /ai/.
    """
    setup_handlers(server_app.web_app)
    server_app.log.info("ai_jupyter_server: extension loaded → routes /ai/*")
