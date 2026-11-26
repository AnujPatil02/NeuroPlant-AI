import React, {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import FactoryScene from "./scene/FactoryScene";

import {
  mergeMachineCollections,
  normalizeMachineCollection,
} from "./data/twinState";

import {
  emitMachineSelected,
  emitSelectionCleared,
  emitTwinReady,
  getBridgeConfig,
  subscribeToBridge,
} from "./bridge/streamlitBridge";

const POLL_INTERVAL = 2000;
const REFRESH_RETRY_INTERVAL = 5000;

function normalizeApiBase(value) {
  return String(value || "").replace(/\/+$/, "");
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json();
}

export default function App() {
  const bridgeConfig = useMemo(() => getBridgeConfig(), []);

  const [apiBaseUrl, setApiBaseUrl] = useState(
    normalizeApiBase(bridgeConfig.apiBaseUrl)
  );

  const [machines, setMachines] = useState({});
  const [selectedMachineId, setSelectedMachineId] = useState(
    bridgeConfig.machineId || bridgeConfig.focusMachineId || null
  );

  const [connectionState, setConnectionState] = useState("connecting");
  const [lastUpdated, setLastUpdated] = useState(null);
  const [lastError, setLastError] = useState(null);

  // ── Refresh the twin cache, then fetch machines ──────────────────
  // The FastAPI /twin/machines endpoint returns 404 when the twin cache
  // is empty (see twin.py's "Twin state is empty. Call POST /twin/refresh
  // first." error). This is by design -- /twin/machines is a read-only
  // view of the OPC-UA state, and refresh is what populates it. So on
  // mount we call POST /twin/refresh once before the polling loop starts,
  // and if /twin/machines still 404s (OPC-UA server not running), we
  // surface the error instead of silently showing zero assets.
  const refreshTwinState = useCallback(async () => {
    try {
      await fetchJson(`${apiBaseUrl}/twin/refresh`, { method: "POST" });
      return true;
    } catch (error) {
      setLastError(`refresh failed: ${error.message}`);
      return false;
    }
  }, [apiBaseUrl]);

  const loadMachineState = useCallback(async () => {
    try {
      const payload = await fetchJson(`${apiBaseUrl}/twin/machines`);
      const normalized = normalizeMachineCollection(payload);

      setMachines((previous) =>
        mergeMachineCollections(previous, normalized)
      );

      setConnectionState("connected");
      setLastUpdated(new Date().toISOString());
      setLastError(null);
    } catch (error) {
      setConnectionState("error");
      setLastError(error.message);
    }
  }, [apiBaseUrl]);

  // ── Mount: emit ready, refresh, start polling ────────────────────
  useEffect(() => {
    emitTwinReady();
  }, []);

  useEffect(() => {
    let cancelled = false;
    let intervalId = null;

    const start = async () => {
      const refreshed = await refreshTwinState();
      if (cancelled) return;

      // Even if refresh failed, try a machine fetch once -- sometimes the
      // cache has been populated by a previous refresh in another
      // browser tab, and we don't want to give up prematurely.
      await loadMachineState();
      if (cancelled) return;

      // Retry refresh quickly if the first attempt failed, then settle
      // into the normal 2s polling interval.
      intervalId = window.setInterval(() => {
        if (!refreshed) {
          refreshTwinState().then(() => loadMachineState());
        } else {
          loadMachineState();
        }
      }, refreshed ? POLL_INTERVAL : REFRESH_RETRY_INTERVAL);
    };

    start();

    return () => {
      cancelled = true;
      if (intervalId) window.clearInterval(intervalId);
    };
  }, [refreshTwinState, loadMachineState]);

  // ── Bridge: respond to messages from Streamlit ──────────────────
  useEffect(() => {
    const unsubscribe = subscribeToBridge((message) => {
      if (message.type === "focus_machine" && message.machineId) {
        setSelectedMachineId(message.machineId);
        return;
      }

      if (message.type === "clear_selection") {
        setSelectedMachineId(null);
        emitSelectionCleared();
        return;
      }

      if (
        message.type === "set_api_base_url" &&
        message.apiBaseUrl !== undefined
      ) {
        setApiBaseUrl(normalizeApiBase(message.apiBaseUrl));
      }
    });

    return unsubscribe;
  }, []);

  const handleSelectMachine = useCallback((machineId) => {
    setSelectedMachineId(machineId);
    emitMachineSelected(machineId);
  }, []);

  const handleClearSelection = useCallback(() => {
    setSelectedMachineId(null);
    emitSelectionCleared();
  }, []);

  return (
    <FactoryScene
      machines={machines}
      selectedMachineId={selectedMachineId}
      onSelectMachine={handleSelectMachine}
      connectionState={connectionState}
      lastUpdated={lastUpdated}
      lastError={lastError}
      apiBaseUrl={apiBaseUrl}
      onClearSelection={handleClearSelection}
    />
  );
}