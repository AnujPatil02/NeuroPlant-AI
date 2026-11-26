import React, { useMemo } from "react";

import {
  getMachineCounts,
} from "../data/twinState";

function formatNumber(value) {
  if (
    value === null ||
    value === undefined ||
    Number.isNaN(Number(value))
  ) {
    return "—";
  }

  return Number(value).toLocaleString();
}

function Metric({
  label,
  value,
}) {
  return (
    <div className="twin-hud-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default function TwinHUD({
  machines = {},
  selectedMachineId,
  connectionState = "connecting",
  lastUpdated,
}) {
  const counts = useMemo(
    () => getMachineCounts(machines),
    [machines]
  );

  const connectionLabel =
    connectionState === "connected"
      ? "LIVE"
      : connectionState === "error"
        ? "OFFLINE"
        : "CONNECTING";

  const selected =
    selectedMachineId
      ? machines[selectedMachineId]
      : null;

  return (
    <div className="twin-hud">
      <div className="twin-hud-topline">
        <div className="twin-hud-title">
          <div className="eyebrow">
            NEUROPLANT AI / DIGITAL TWIN
          </div>

          <h1>
            PRECISION MOBILITY FACTORY
          </h1>
        </div>

        <div
          className={`twin-connection ${
            connectionState === "connected"
              ? "live"
              : connectionState === "error"
                ? "warning"
                : "connecting"
          }`}
        >
          <span className="connection-dot" />
          <span>{connectionLabel}</span>
        </div>
      </div>

      <div className="twin-hud-metrics">
        <Metric
          label="ASSETS"
          value={formatNumber(counts.total)}
        />

        <Metric
          label="RUNNING"
          value={formatNumber(counts.running)}
        />

        <Metric
          label="WARNING"
          value={formatNumber(counts.warning)}
        />

        <Metric
          label="FAULT"
          value={formatNumber(counts.fault)}
        />

        <Metric
          label="MAINTENANCE"
          value={formatNumber(
            counts.maintenance
          )}
        />
      </div>

      <div className="twin-hud-context">
        <div className="context-block">
          <span className="context-label">
            SOURCE
          </span>

          <strong>
            OPC-UA TELEMETRY
          </strong>
        </div>

        <div className="context-block">
          <span className="context-label">
            UPDATE
          </span>

          <strong>
            {lastUpdated
              ? new Date(
                  lastUpdated
                ).toLocaleTimeString(
                  [],
                  {
                    hour: "2-digit",
                    minute: "2-digit",
                    second: "2-digit",
                  }
                )
              : "—"}
          </strong>
        </div>

        {selected && (
          <div className="context-block selected-context">
            <span className="context-label">
              SELECTED
            </span>

            <strong>
              {selected.machineId}
            </strong>
          </div>
        )}
      </div>
    </div>
  );
}