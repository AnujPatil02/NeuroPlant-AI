const BRIDGE_EVENT = "neuroplant-digital-twin";

// Default FastAPI base URL when nothing overrides it. Matches the value
// in streamlit_integration/digital_twin_embed.py so an out-of-the-box
// `npm run dev` + uvicorn on 8000 also works without any extra config.
const DEFAULT_API_BASE_URL = "http://localhost:8000";

let listeners = new Set();

function getParentWindow() {
  try {
    if (window.parent && window.parent !== window) {
      return window.parent;
    }
  } catch {
    // Ignore cross-frame access issues.
  }

  return window;
}

function dispatchToParent(payload) {
  try {
    getParentWindow().postMessage(
      {
        source: "neuroplant-digital-twin",
        ...payload,
      },
      "*"
    );
  } catch {
    // Bridge communication is optional when running standalone.
  }
}

function handleMessage(event) {
  const data = event?.data;

  if (!data || typeof data !== "object") {
    return;
  }

  if (
    data.source !== "neuroplant-streamlit" &&
    data.type !== BRIDGE_EVENT
  ) {
    return;
  }

  listeners.forEach((listener) => {
    try {
      listener(data);
    } catch {
      // One listener must not break the remaining bridge listeners.
    }
  });
}

if (typeof window !== "undefined") {
  window.addEventListener("message", handleMessage);
}

/**
 * Reads bridge configuration.
 *
 * FIX: previous version ONLY read from window.location.search. When the
 * twin is embedded via Streamlit srcdoc (the standard deployment for this
 * project), there is no query string on window.location -- the params
 * are injected into window.__NEUROPLANT_BRIDGE_PARAMS__ by a bootstrap
 * script in the iframe head (see digital_twin_embed.py). This function
 * now checks that override first, then falls back to location.search,
 * then to DEFAULT_API_BASE_URL, so the app always has a sensible target.
 */
export function getBridgeConfig() {
  if (typeof window === "undefined") {
    return {
      apiBaseUrl: DEFAULT_API_BASE_URL,
      machineId: null,
      focusMachineId: null,
    };
  }

  // 1. Streamlit-injected override (srcdoc case)
  const override = window.__NEUROPLANT_BRIDGE_PARAMS__;
  if (override && typeof override === "object") {
    return {
      apiBaseUrl: override.api_base_url || DEFAULT_API_BASE_URL,
      machineId: override.machine || null,
      focusMachineId: override.focus_machine || null,
    };
  }

  // 2. Query string (standalone dev via Vite or direct iframe URL)
  const params = new URLSearchParams(window.location.search);
  const apiBaseFromQuery = params.get("api_base_url");

  return {
    apiBaseUrl: apiBaseFromQuery || DEFAULT_API_BASE_URL,
    machineId: params.get("machine") || null,
    focusMachineId: params.get("focus_machine") || null,
  };
}

export function subscribeToBridge(listener) {
  if (typeof listener !== "function") {
    return () => {};
  }

  listeners.add(listener);

  return () => {
    listeners.delete(listener);
  };
}

export function emitMachineSelected(machineId) {
  dispatchToParent({
    type: "selected_machine",
    machineId,
  });
}

export function emitTwinReady() {
  dispatchToParent({
    type: "twin_ready",
  });
}

export function emitTwinState(payload) {
  dispatchToParent({
    type: "twin_state",
    payload,
  });
}

export function emitSimulationRequest(payload) {
  dispatchToParent({
    type: "simulate_machine",
    payload,
  });
}

export function emitCameraPreset(preset) {
  dispatchToParent({
    type: "camera_preset",
    preset,
  });
}

export function emitSelectionCleared() {
  dispatchToParent({
    type: "selection_cleared",
  });
}