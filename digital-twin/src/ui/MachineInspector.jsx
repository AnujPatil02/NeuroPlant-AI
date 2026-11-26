import React from "react";
import { deriveMachineStatus } from "../data/twinState";

function format(value, digits = 1) {
  if (
    value === null ||
    value === undefined ||
    Number.isNaN(Number(value))
  ) {
    return "—";
  }
  return Number(value).toFixed(digits);
}

function SensorRow({ label, value, unit }) {
  return (
    <div className="inspector-sensor">
      <span>{label}</span>
      <strong>
        {value}
        {unit && <small>{unit}</small>}
      </strong>
    </div>
  );
}

function StateRow({ label, value }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default function MachineInspector({ machine, onClose, onFocus }) {
  if (!machine) return null;

  const status = deriveMachineStatus(machine);

  // Status class for styling. Map twin vocabulary to lowercase for CSS:
  // FAULT -> fault, WARNING -> warning, etc.
  const statusClass = status.toLowerCase();

  return (
    <aside className="machine-inspector">
      <div className="inspector-header">
        <div>
          <span className="inspector-eyebrow">MACHINE INSPECTOR</span>
          <h2>{machine.machineId}</h2>
          {machine.line && (
            <span className="inspector-line-label">{machine.line}</span>
          )}
        </div>
        <button
          type="button"
          className="inspector-close"
          onClick={onClose}
          aria-label="Close inspector"
        >
          ×
        </button>
      </div>

      <div className="inspector-status-row">
        <span className={`inspector-status ${statusClass}`}>
          <i />
          {status}
        </span>
        <button
          type="button"
          className="inspector-focus"
          onClick={() => onFocus?.(machine.machineId)}
        >
          FOCUS
        </button>
      </div>

      <section className="inspector-section">
        <div className="inspector-section-title">
          <span>SENSOR TELEMETRY</span>
          <span className="section-line" />
        </div>

        <div className="inspector-grid">
          <SensorRow
            label="Temperature"
            value={format(machine.temperature)}
            unit="°C"
          />
          <SensorRow
            label="Vibration"
            value={format(machine.vibration)}
            unit="mm/s"
          />
          <SensorRow
            label="RPM"
            value={format(machine.rpm, 0)}
            unit="RPM"
          />
          <SensorRow
            label="Current"
            value={format(machine.currentDraw)}
            unit="A"
          />
          <SensorRow
            label="Pressure"
            value={format(machine.pressure)}
            unit="bar"
          />
          <SensorRow
            label="Humidity"
            value={format(machine.humidity)}
            unit="%"
          />
        </div>
      </section>

      <section className="inspector-section">
        <div className="inspector-section-title">
          <span>MACHINE STATE</span>
          <span className="section-line" />
        </div>

        <div className="inspector-state-list">
          <StateRow
            label="Operating Mode"
            value={machine.operatingMode || "—"}
          />
          <StateRow
            label="Production Count"
            value={
              machine.productionCount !== null
                ? Number(machine.productionCount).toLocaleString()
                : "—"
            }
          />
          <StateRow
            label="Maintenance"
            value={machine.maintenanceStatus || "—"}
          />
        </div>
      </section>

      <section className="inspector-section">
        <div className="inspector-section-title">
          <span>DIGITAL TWIN</span>
          <span className="section-line" />
        </div>

        <div className="inspector-production">
          <StateRow
            label="OEE Contribution"
            value={
              machine.oee !== null && machine.oee !== undefined
                ? `${format(machine.oee)}%`
                : "—"
            }
          />
          <StateRow
            label="RUL"
            value={
              machine.rulDays !== null && machine.rulDays !== undefined
                ? `${format(machine.rulDays)} d`
                : "—"
            }
          />
        </div>
      </section>

      <div className="inspector-footer">
        <span>STATE REPLICATION</span>
        <strong>OPC-UA</strong>
      </div>
    </aside>
  );
}