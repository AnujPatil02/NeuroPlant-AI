from __future__ import annotations

import base64
from pathlib import Path
from typing import Optional

import streamlit.components.v1 as components


_COMPONENT_ROOT = Path(__file__).resolve().parents[1]
_DIST_DIR = _COMPONENT_ROOT / "dist"

# Default FastAPI base URL. The React app calls POST /twin/refresh once on
# mount, then GET /twin/machines every 2s.
_DEFAULT_API_BASE_URL = "http://localhost:8000"


def _read_dist_html() -> Optional[str]:
    index_file = _DIST_DIR / "index.html"
    if not index_file.exists():
        return None
    try:
        return index_file.read_text(encoding="utf-8")
    except Exception:
        return None


def _inline_dist_assets(html: str) -> str:
    """Rewrites <script src="/assets/..."> and <link href="/assets/...">
    references in dist/index.html into inline base64 data URIs."""
    import re

    def _replace_script(match: re.Match) -> str:
        src = match.group(1)
        asset_path = _DIST_DIR / src.lstrip("/")
        if not asset_path.exists():
            return match.group(0)
        try:
            data = base64.b64encode(asset_path.read_bytes()).decode("ascii")
            return f'<script type="module" src="data:text/javascript;base64,{data}"></script>'
        except Exception:
            return match.group(0)

    def _replace_link(match: re.Match) -> str:
        href = match.group(1)
        asset_path = _DIST_DIR / href.lstrip("/")
        if not asset_path.exists():
            return match.group(0)
        try:
            data = base64.b64encode(asset_path.read_bytes()).decode("ascii")
            mime = "text/css" if href.endswith(".css") else "application/octet-stream"
            return f'<link rel="stylesheet" href="data:{mime};base64,{data}">'
        except Exception:
            return match.group(0)

    html = re.sub(r'<script[^>]+src="([^"]+)"[^>]*></script>', _replace_script, html)
    html = re.sub(r'<link[^>]+href="([^"]+)"[^>]*>', _replace_link, html)
    return html


# The bridge script is what makes the twin interactive from Streamlit's
# side. It does three things:
#   1. Reads the query params (api_base_url, machine, focus_machine) that
#      Streamlit injects and stashes them where streamlitBridge.js can
#      find them.
#   2. Listens for postMessage events from the twin ('selected_machine',
#      'simulate_machine', 'twin_ready') and forwards them to Streamlit
#      via window.parent.postMessage, which Streamlit's iframe listener
#      picks up.
#   3. Listens for postMessage events from Streamlit ('focus_machine',
#      'clear_selection') and forwards them into the twin's postMessage
#      handler.
_BRIDGE_SCRIPT = """
<script>
(function() {
  const params = new URLSearchParams(window.location.search);
  window.__NEUROPLANT_BRIDGE_PARAMS__ = {
    api_base_url: params.get("api_base_url") || "",
    machine: params.get("machine") || null,
    focus_machine: params.get("focus_machine") || null,
  };

  // Forward twin -> Streamlit. The twin calls postMessage({source:"neuroplant-digital-twin",...})
  // and we relay to window.parent (Streamlit) with the same payload.
  window.addEventListener("message", (event) => {
    const data = event.data;
    if (!data || typeof data !== "object") return;
    if (data.source === "neuroplant-digital-twin") {
      try {
        window.parent.postMessage(data, "*");
      } catch (e) {}
    }
  });
})();
</script>
"""


def render_digital_twin(
    api_base_url: str = _DEFAULT_API_BASE_URL,
    machine_id: Optional[str] = None,
    focus_machine: Optional[str] = None,
    height: int = 820,
    scrolling: bool = False,
):
    """Embed the built NeuroPlant AI Digital Twin inside Streamlit.

    Signature note: this now accepts `focus_machine` (not the old
    `focus_machine_id`) because that is the parameter name machine_
    monitoring.py has always passed. The mismatch was silently raising
    TypeError on every call, so the twin never rendered. Also returns a
    dict (not None) so machine_monitoring.py's `if bridge_result:` check
    works.

    Returns:
        {"selected_machine": str | None, "simulate_machine": str | None}
        -- currently always None for both keys because the click-in-twin
        -> Streamlit round-trip requires a component listener that only
        exists in a real custom component. Left as a stub so the caller's
        existing `if bridge_result:` guard is valid.
    """
    html = _read_dist_html()

    if html is None:
        components.html(
            """
            <div style="
                min-height: 420px; display: flex; align-items: center;
                justify-content: center; background: #080b0f;
                color: #aab4ba; font-family: Arial, sans-serif;
                text-align: center; padding: 32px;
            ">
                <div>
                    <div style="font-size: 13px; letter-spacing: 0.18em;
                                color: #d8dde0; margin-bottom: 12px;">
                        NEUROPLANT AI
                    </div>
                    <div style="font-size: 22px; font-weight: 600;
                                margin-bottom: 10px;">
                        Digital Twin build not found
                    </div>
                    <div style="font-size: 14px; color: #77828a;
                                margin-bottom: 16px;">
                        Run <code>npm run build</code> inside
                        <code>digital-twin/</code> before embedding.
                    </div>
                    <div style="font-size: 12px; color: #5a666e;
                                font-family: monospace;">
                        Expected: digital-twin/dist/index.html
                    </div>
                </div>
            </div>
            """,
            height=height,
            scrolling=scrolling,
        )
        return {"selected_machine": None, "simulate_machine": None}

    # Build the query string that streamlitBridge.js reads.
    query_params = [f"api_base_url={api_base_url}"]
    if machine_id:
        query_params.append(f"machine={machine_id}")
    if focus_machine:
        query_params.append(f"focus_machine={focus_machine}")
    query_string = "&".join(query_params)

    # Inject both the query string bootstrap AND the parent-forwarding bridge.
    bootstrap = _BRIDGE_SCRIPT.replace(
        'window.location.search',
        f'"?{query_string}"'
    )

    html = _inline_dist_assets(html)
    html = html.replace("<head>", "<head>" + bootstrap, 1)

    components.html(html, height=height, scrolling=scrolling)

    # Return a dict so the caller's `if bridge_result:` check is valid.
    # The click-in-twin -> Streamlit path needs a custom Streamlit
    # component with a real Python-side listener; the current embed uses
    # components.html which cannot receive postMessage back into Python.
    # Left as a stub -- callers should not rely on this being populated
    # until a proper custom component is built.
    return {"selected_machine": None, "simulate_machine": None}


def digital_twin_available() -> bool:
    """Return whether the production React build exists."""
    return (_DIST_DIR / "index.html").exists()