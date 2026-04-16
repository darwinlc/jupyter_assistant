/**
 * custom.js  –  AI Jupyter Server hotkeys for JupyterLab
 *
 * Place this file at:
 *   ~/.jupyter/custom/custom.js
 *
 * It is loaded automatically by JupyterLab on every page load.
 * No build step, no npm, no restart needed after editing this file
 * (just reload the browser tab).
 *
 * Default hotkeys:
 *   Ctrl+Shift+Space  →  complete selected text / whole file
 *   Ctrl+Shift+E      →  edit   (prompts for instruction)
 *   Ctrl+Shift+V      →  review
 *   Ctrl+Shift+A      →  ask    (prompts for question)
 *
 * Change the HOTKEYS map below to remap anything.
 */

(function () {
  "use strict";

  // ── Configuration ──────────────────────────────────────────────────────────
  const BASE_URL = (window.location.origin +
    (window.jupyter_config_data
      ? window.jupyter_config_data.baseUrl || "/"
      : "/")).replace(/\/$/, "");

  const API = {
    complete : BASE_URL + "/ai/complete",
    edit     : BASE_URL + "/ai/edit",
    review   : BASE_URL + "/ai/review",
    ask      : BASE_URL + "/ai/ask",
    ping     : BASE_URL + "/ai/ping",
  };

  // Remap any of these to change hotkeys.
  // Format: Ctrl / Shift / Alt followed by the key name (case-insensitive).
  const HOTKEYS = {
    complete : { ctrl: true,  shift: true,  alt: false, key: " "  },  // Ctrl+Shift+Space
    edit     : { ctrl: true,  shift: true,  alt: false, key: "e"  },  // Ctrl+Shift+E
    review   : { ctrl: true,  shift: true,  alt: false, key: "v"  },  // Ctrl+Shift+V
    ask      : { ctrl: true,  shift: true,  alt: false, key: "a"  },  // Ctrl+Shift+A
  };

  // ── Helpers ────────────────────────────────────────────────────────────────

  function matchesHotkey(e, hk) {
    return (
      e.ctrlKey  === hk.ctrl  &&
      e.shiftKey === hk.shift &&
      e.altKey   === hk.alt   &&
      e.key.toLowerCase() === hk.key.toLowerCase()
    );
  }

  /**
   * Returns the xsrf token from the JupyterLab cookie, required for POST requests.
   */
  function xsrfToken() {
    const match = document.cookie.match(/\b_xsrf=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  /**
   * POST to a server extension endpoint.
   * @param {string} url
   * @param {object} payload
   * @returns {Promise<{result?: string, error?: string}>}
   */
  async function callAI(url, payload) {
    const resp = await fetch(url, {
      method  : "POST",
      headers : {
        "Content-Type" : "application/json",
        "X-XSRFToken"  : xsrfToken(),
      },
      body: JSON.stringify(payload),
    });
    return resp.json();
  }

  // ── Editor access (CodeMirror 6 — JupyterLab 4.x) ─────────────────────────

  /**
   * Walk the JupyterLab shell to find the active CodeMirror 6 editor view.
   * Works for .py, .md, .txt, .sql, … in the file editor, and for notebook cells.
   */
  function getEditorView() {
    try {
      const app = window.jupyterapp;
      if (!app) return null;

      const widget = app.shell.currentWidget;
      if (!widget) return null;

      // ── File editor (EditorPanel) ────────────────────────────────────────
      // JupyterLab wraps the CodeMirror view in widget.content.editor._editor
      const content = widget.content;
      if (content && content.editor && content.editor._editor) {
        return content.editor._editor;  // CodeMirror EditorView
      }

      // ── Notebook active cell ──────────────────────────────────────────────
      if (content && content.activeCell) {
        const cellEditor = content.activeCell.editor;
        if (cellEditor && cellEditor._editor) return cellEditor._editor;
      }
    } catch (e) {
      console.warn("AI Jupyter: could not get editor view", e);
    }
    return null;
  }

  /**
   * Returns {text, hasSelection, from, to} for the active editor.
   * If text is selected, returns the selection; otherwise returns the whole document.
   */
  function getEditorContent(view) {
    const state = view.state;
    const sel   = state.selection.main;
    const hasSelection = sel.from !== sel.to;
    const text  = hasSelection
      ? state.sliceDoc(sel.from, sel.to)
      : state.doc.toString();
    return { text, hasSelection, from: sel.from, to: sel.to };
  }

  /**
   * Insert or replace text in the editor.
   * If hasSelection, replaces the selection; otherwise replaces the whole doc.
   */
  function setEditorContent(view, newText, hasSelection, from, to) {
    const state  = view.state;
    const change = hasSelection
      ? { from, to, insert: newText }
      : { from: 0, to: state.doc.length, insert: newText };
    view.dispatch({ changes: change });
  }

  /**
   * Detect the file type from the current widget's title / path.
   * Falls back to "txt".
   */
  function detectFileType() {
    try {
      const app    = window.jupyterapp;
      const widget = app && app.shell.currentWidget;
      if (!widget) return "txt";

      // File editor: widget.context.path = "path/to/file.py"
      const ctx = widget.context;
      if (ctx && ctx.path) {
        const parts = ctx.path.split(".");
        return parts.length > 1 ? parts[parts.length - 1] : "txt";
      }

      // Notebook
      if (widget.content && widget.content.activeCell) return "ipynb";
    } catch (e) { /* ignore */ }
    return "txt";
  }

  // ── Overlay UI ────────────────────────────────────────────────────────────

  /** Show a non-blocking toast notification in the bottom-right corner. */
  function toast(message, durationMs = 3000) {
    let el = document.getElementById("ai-jupyter-toast");
    if (!el) {
      el = document.createElement("div");
      el.id = "ai-jupyter-toast";
      Object.assign(el.style, {
        position      : "fixed",
        bottom        : "24px",
        right         : "24px",
        background    : "#1e1e2e",
        color         : "#e0deff",
        border        : "1px solid #7c6af7",
        borderRadius  : "8px",
        padding       : "10px 16px",
        fontFamily    : "monospace",
        fontSize      : "13px",
        zIndex        : "99999",
        boxShadow     : "0 4px 20px rgba(0,0,0,0.4)",
        transition    : "opacity 0.3s",
        pointerEvents : "none",
      });
      document.body.appendChild(el);
    }
    el.textContent = message;
    el.style.opacity = "1";
    clearTimeout(el._timer);
    el._timer = setTimeout(() => { el.style.opacity = "0"; }, durationMs);
  }

  // ── Action handlers ────────────────────────────────────────────────────────

  async function doComplete() {
    const view = getEditorView();
    if (!view) { toast("⚠️  No active editor found"); return; }

    const { text, hasSelection, from, to } = getEditorContent(view);
    const fileType = detectFileType();

    toast("⏳  Completing…");
    const data = await callAI(API.complete, { content: text, file_type: fileType });
    if (data.error) { toast("❌  " + data.error); return; }
    setEditorContent(view, data.result, hasSelection, from, to);
    toast("✅  Completed");
  }

  async function doEdit() {
    const view = getEditorView();
    if (!view) { toast("⚠️  No active editor found"); return; }

    const instruction = prompt("✏️  Edit instruction:");
    if (!instruction) return;

    const { text, hasSelection, from, to } = getEditorContent(view);
    const fileType = detectFileType();

    toast("⏳  Editing…");
    const data = await callAI(API.edit, {
      content     : text,
      instruction : instruction,
      file_type   : fileType,
    });
    if (data.error) { toast("❌  " + data.error); return; }
    setEditorContent(view, data.result, hasSelection, from, to);
    toast("✅  Edit applied");
  }

  async function doReview() {
    const view = getEditorView();
    if (!view) { toast("⚠️  No active editor found"); return; }

    const { text } = getEditorContent(view);
    const fileType = detectFileType();

    toast("⏳  Reviewing…");
    const data = await callAI(API.review, { content: text, file_type: fileType });
    if (data.error) { toast("❌  " + data.error); return; }

    // Show review in a modal-style panel
    showReviewPanel(data.result);
    toast("✅  Review ready");
  }

  async function doAsk() {
    const question = prompt("💬  Your question:");
    if (!question) return;

    const fileType = detectFileType();
    toast("⏳  Thinking…");
    const data = await callAI(API.ask, { question, file_type: fileType });
    if (data.error) { toast("❌  " + data.error); return; }
    showReviewPanel(data.result);
    toast("✅  Answer ready");
  }

  // ── Review / answer panel ─────────────────────────────────────────────────

  function showReviewPanel(markdown) {
    // Remove existing panel
    const old = document.getElementById("ai-jupyter-panel");
    if (old) old.remove();

    const panel = document.createElement("div");
    panel.id = "ai-jupyter-panel";
    Object.assign(panel.style, {
      position     : "fixed",
      top          : "60px",
      right        : "24px",
      width        : "420px",
      maxHeight    : "70vh",
      overflowY    : "auto",
      background   : "#0f0f1a",
      color        : "#e0deff",
      border       : "1px solid #7c6af7",
      borderRadius : "10px",
      padding      : "16px 20px",
      fontFamily   : "monospace",
      fontSize     : "13px",
      lineHeight   : "1.6",
      zIndex       : "99998",
      boxShadow    : "0 8px 32px rgba(0,0,0,0.6)",
      whiteSpace   : "pre-wrap",
    });

    // Close button
    const close = document.createElement("button");
    close.textContent = "✕";
    Object.assign(close.style, {
      position   : "absolute",
      top        : "10px",
      right      : "12px",
      background : "none",
      border     : "none",
      color      : "#7c6af7",
      cursor     : "pointer",
      fontSize   : "16px",
    });
    close.onclick = () => panel.remove();
    panel.appendChild(close);

    // Simple markdown → HTML (bold, code, headings, bullets)
    const html = markdown
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/^#{1,3} (.+)$/gm, "<strong>$1</strong>")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, '<code style="background:#1e1e2e;padding:1px 4px;border-radius:3px">$1</code>')
      .replace(/^- (.+)$/gm, "  • $1");

    const content = document.createElement("div");
    content.innerHTML = html;
    panel.appendChild(content);
    document.body.appendChild(panel);
  }

  // ── Keyboard listener ─────────────────────────────────────────────────────

  // Remove previous listener on hot-reload
  if (window._aiJupyterKeydown) {
    document.removeEventListener("keydown", window._aiJupyterKeydown, true);
  }

  window._aiJupyterKeydown = function (e) {
    if (matchesHotkey(e, HOTKEYS.complete)) {
      e.preventDefault(); e.stopPropagation(); doComplete();
    } else if (matchesHotkey(e, HOTKEYS.edit)) {
      e.preventDefault(); e.stopPropagation(); doEdit();
    } else if (matchesHotkey(e, HOTKEYS.review)) {
      e.preventDefault(); e.stopPropagation(); doReview();
    } else if (matchesHotkey(e, HOTKEYS.ask)) {
      e.preventDefault(); e.stopPropagation(); doAsk();
    }
  };

  document.addEventListener("keydown", window._aiJupyterKeydown, true);

  // ── Startup ping ──────────────────────────────────────────────────────────
  fetch(API.ping)
    .then(r => r.json())
    .then(d => console.log("AI Jupyter Server ready:", d))
    .catch(() => console.warn("AI Jupyter Server: extension not running — did you install and restart?"));

})();
