const MACHINE_STATUS = [
  "RUNNING",
  "IDLE",
  "WARNING",
  "FAULT",
  "MAINTENANCE",
  "OFFLINE",
];

/**
 * Coerces a value to a number, tolerating:
 *   - actual numbers (returned as-is)
 *   - numeric strings ("3.5", "2790")
 *   - formatted strings with units ("3.5 DAYS", "68.2°C", "2,790", "41.0%")
 *   - empty/null/undefined/"—" (returns the fallback)
 *
 * The API now returns raw numbers for everything, but this coercion
 * keeps the client resilient if a future endpoint returns a formatted
 * string by mistake, and lets the initial render (before /twin/machines
 * has returned) still work with the fallback values.
 */
function toNumber(value, fallback = null) {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }

  // Already a number
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : fallback;
  }

  // Coerce to string and strip thousands separators, then parse the
  // first numeric run. This handles "3.5 DAYS", "68.2°C", "2,790", "41.0%".
  const cleaned = String(value).replace(/,/g, "").trim();
  if (!cleaned || cleaned === "—" || cleaned === "-" || cleaned === "N/A") {
    return fallback;
  }
  const match = cleaned.match(/[-+]?\d*\.?\d+/);
  if (!match) {
    return fallback;
  }
  const number = Number(match[0]);
  return Number.isFinite(number) ? number : fallback;
}

function normalizeId(machineId) {
  return String(machineId || "").trim().toUpperCase();
}

/**
 * Maps the Python-side status strings ("online", "warning", "critical")
 * to the twin's internal status vocabulary ("RUNNING", "WARNING",
 * "FAULT"). The FastAPI /twin/machines response now includes a `status`
 * field for every machine sourced from the shared _MACHINE_HEALTH_STATIC
 * table, so we read THAT instead of trying to infer status from
 * maintenance/operating_mode strings.
 */
function mapBackendStatus(rawStatus) {
  const s = String(rawStatus || "").toLowerCase().trim();
  if (s === "critical" || s === "fault" || s === "failed") return "FAULT";
  if (s === "warning" || s === "warn") return "WARNING";
  if (s === "maintenance" || s === "pm" || s === "service") return "MAINTENANCE";
  if (s === "offline" || s === "disconnected") return "OFFLINE";
  if (s === "idle" || s === "stopped") return "IDLE";
  if (s === "online" || s === "running" || s === "active") return "RUNNING";
  return null;
}

export function deriveMachineStatus(machine = {}) {
  // Priority 1: explicit `status` field from the enriched FastAPI
  // response (sourced from _MACHINE_HEALTH_STATIC). This is what makes
  // CNC-02 show FAULT and CNC-07/08 show WARNING instead of RUNNING.
  const backendStatus = mapBackendStatus(machine.status);
  if (backendStatus) {
    return backendStatus;
  }

  // Priority 2: legacy fallback — infer from maintenance/operating_mode
  // strings. Only reached if the API response didn't include a status
  // field, which happens for the initial render before /twin/machines
  // has returned.
  const maintenance = String(
    machine.maintenanceStatus ?? machine.maintenance_status ?? ""
  ).toUpperCase();
  const operatingMode = String(
    machine.operatingMode ?? machine.operating_mode ?? ""
  ).toUpperCase();

  if (
    maintenance.includes("MAINTENANCE") ||
    maintenance === "PM" ||
    maintenance === "SERVICE"
  ) {
    return "MAINTENANCE";
  }
  if (
    operatingMode.includes("FAULT") ||
    operatingMode.includes("ERROR") ||
    operatingMode.includes("FAILED")
  ) {
    return "FAULT";
  }
  if (
    operatingMode.includes("WARNING") ||
    operatingMode.includes("WARN")
  ) {
    return "WARNING";
  }
  if (
    operatingMode.includes("OFFLINE") ||
    operatingMode.includes("DISCONNECTED")
  ) {
    return "OFFLINE";
  }
  if (
    operatingMode.includes("IDLE") ||
    operatingMode.includes("STOPPED")
  ) {
    return "IDLE";
  }
  if (
    operatingMode.includes("RUN") ||
    operatingMode.includes("ACTIVE") ||
    operatingMode.includes("PRODUCTION")
  ) {
    return "RUNNING";
  }

  return "IDLE";
}

// Known machine ID patterns. Rejects server-infrastructure nodes.
const MACHINE_ID_PATTERN =
  /^(CNC|ASM|WASH|DEBURR|HEAT|QC|COMP|COOL|SUBSTATION|ZONE)[-_]?[0-9A-Z_]*$/i;

export function normalizeMachine(machineId, raw = {}) {
  const id = normalizeId(
    machineId || raw.machineId || raw.machine_id || raw.id || raw.name
  );

  if (!id) return null;
  if (!MACHINE_ID_PATTERN.test(id)) return null;

  const machine = {
    ...raw,
    machineId: id,

    // Carry the raw backend status through for deriveMachineStatus().
    status:
      raw.status ??
      raw.machineStatus ??
      raw.machine_status ??
      null,

    operatingMode:
      raw.operatingMode ?? raw.operating_mode ?? "IDLE",

    maintenanceStatus:
      raw.maintenanceStatus ?? raw.maintenance_status ?? "NORMAL",

    productionCount: toNumber(
      raw.productionCount ??
        raw.production_count ??
        raw.production ??
        0,
      0
    ),

    temperature: toNumber(raw.temperature ?? raw.temp),
    vibration: toNumber(raw.vibration ?? raw.vibration_rms),
    rpm: toNumber(raw.rpm ?? raw.spindle_rpm),

    currentDraw: toNumber(
      raw.currentDraw ?? raw.current_draw ?? raw.current
    ),

    pressure: toNumber(raw.pressure),
    humidity: toNumber(raw.humidity),

    // Both names supported so callers can read either.
    oee: toNumber(
      raw.oee ?? raw.oee_contribution ?? raw.oeeContribution
    ),
    oeeContribution: toNumber(
      raw.oeeContribution ?? raw.oee_contribution ?? raw.oee
    ),

    rulDays: toNumber(
      raw.rulDays ?? raw.rul_days ?? raw.remaining_useful_life
    ),

    healthScore: toNumber(raw.healthScore ?? raw.health_score),
    anomaly: Boolean(raw.anomaly ?? raw.is_anomaly ?? false),
    line: raw.line ?? raw.line_id ?? raw.lineName ?? "",

    lastUpdated: raw.lastUpdated ?? raw.last_updated ?? null,
  };

  machine.status = deriveMachineStatus(machine);

  return machine;
}

export function normalizeMachineCollection(payload) {
  if (!payload) return {};

  let collection = payload;

  if (Array.isArray(payload)) {
    collection = payload;
  } else if (Array.isArray(payload.machines)) {
    collection = payload.machines;
  } else if (payload.machines && typeof payload.machines === "object") {
    collection = payload.machines;
  } else if (Array.isArray(payload.data)) {
    collection = payload.data;
  } else if (payload.data && typeof payload.data === "object") {
    collection = payload.data;
  }

  const normalized = {};

  if (Array.isArray(collection)) {
    collection.forEach((machine) => {
      const normalizedMachine = normalizeMachine(
        machine?.machineId ||
          machine?.machine_id ||
          machine?.id ||
          machine?.name,
        machine
      );
      if (normalizedMachine) {
        normalized[normalizedMachine.machineId] = normalizedMachine;
      }
    });
    return normalized;
  }

  if (typeof collection === "object") {
    Object.entries(collection).forEach(([machineId, machine]) => {
      const normalizedMachine = normalizeMachine(machineId, machine || {});
      if (normalizedMachine) {
        normalized[normalizedMachine.machineId] = normalizedMachine;
      }
    });
  }

  return normalized;
}

export function mergeMachineCollections(previous = {}, incoming = {}) {
  const next = { ...previous };

  Object.entries(incoming || {}).forEach(([machineId, machine]) => {
    next[machineId] = {
      ...(next[machineId] || {}),
      ...machine,
      machineId,
    };
    next[machineId].status = deriveMachineStatus(next[machineId]);
  });

  return next;
}

export function getSelectedMachine(machines = {}, selectedMachineId) {
  if (!selectedMachineId) return null;
  return machines[selectedMachineId] || null;
}

export function getMachineCounts(machines = {}) {
  const values = Object.values(machines || {});
  const counts = {
    total: values.length,
    running: 0,
    idle: 0,
    warning: 0,
    fault: 0,
    maintenance: 0,
    offline: 0,
  };

  values.forEach((machine) => {
    const status = deriveMachineStatus(machine);
    switch (status) {
      case "RUNNING": counts.running += 1; break;
      case "WARNING": counts.warning += 1; break;
      case "FAULT": counts.fault += 1; break;
      case "MAINTENANCE": counts.maintenance += 1; break;
      case "OFFLINE": counts.offline += 1; break;
      case "IDLE":
      default: counts.idle += 1; break;
    }
  });

  return counts;
}

export function getMachineStatusSummary(machines = {}) {
  const counts = getMachineCounts(machines);
  return [
    { key: "running", label: "RUNNING", value: counts.running },
    { key: "warning", label: "WARNING", value: counts.warning },
    { key: "fault", label: "FAULT", value: counts.fault },
    { key: "maintenance", label: "MAINTENANCE", value: counts.maintenance },
    { key: "idle", label: "IDLE", value: counts.idle },
    { key: "offline", label: "OFFLINE", value: counts.offline },
  ];
}

export function isKnownMachineStatus(status) {
  return MACHINE_STATUS.includes(String(status || "").toUpperCase());
}