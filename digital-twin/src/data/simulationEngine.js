const DEFAULTS = {
    horizonHours: 8,
    currentOee: 82,
    idealUnitsPerHour: 48,
    scheduledDowntimeHours: 0,
    machineHealthFactor: 1,
  };
  
  function clamp(value, min, max) {
    return Math.min(
      Math.max(value, min),
      max
    );
  }
  
  function numberOrDefault(value, fallback) {
    const number = Number(value);
  
    return Number.isFinite(number)
      ? number
      : fallback;
  }
  
  export function simulateProduction({
    lineId = "LINE-01",
    currentOee = DEFAULTS.currentOee,
    idealUnitsPerHour =
      DEFAULTS.idealUnitsPerHour,
    horizonHours = DEFAULTS.horizonHours,
    scheduledDowntimeHours =
      DEFAULTS.scheduledDowntimeHours,
    machineHealthFactor =
      DEFAULTS.machineHealthFactor,
  } = {}) {
    const oee = clamp(
      numberOrDefault(
        currentOee,
        DEFAULTS.currentOee
      ),
      0,
      100
    );
  
    const idealRate = Math.max(
      0,
      numberOrDefault(
        idealUnitsPerHour,
        DEFAULTS.idealUnitsPerHour
      )
    );
  
    const horizon = Math.max(
      0,
      numberOrDefault(
        horizonHours,
        DEFAULTS.horizonHours
      )
    );
  
    const downtime = clamp(
      numberOrDefault(
        scheduledDowntimeHours,
        DEFAULTS.scheduledDowntimeHours
      ),
      0,
      horizon
    );
  
    const health = clamp(
      numberOrDefault(
        machineHealthFactor,
        DEFAULTS.machineHealthFactor
      ),
      0,
      1
    );
  
    const productiveHours =
      Math.max(
        0,
        horizon - downtime
      );
  
    const estimatedOee =
      (oee / 100) * health;
  
    const projectedTotalUnits =
      Math.round(
        idealRate *
          productiveHours *
          estimatedOee
      );
  
    const baselineUnits =
      Math.round(
        idealRate *
          horizon *
          (oee / 100)
      );
  
    const productionLoss =
      Math.max(
        0,
        baselineUnits -
          projectedTotalUnits
      );
  
    return {
      lineId,
      horizonHours: horizon,
      scheduledDowntimeHours:
        downtime,
      productiveHours,
      currentOee: oee,
      machineHealthFactor: health,
      estimatedOee:
        estimatedOee * 100,
      projectedTotalUnits,
      baselineUnits,
      productionLoss,
      constraintFlagged:
        productionLoss > 0,
      constraintMessage:
        productionLoss > 0
          ? `${productionLoss.toLocaleString()} units below baseline`
          : "No production constraint detected",
    };
  }
  
  export function simulateMachineImpact({
    machineId,
    rulDays = null,
    unitsPerHour = 48,
    productValuePerUnit = 1,
    downtimeHours = 1,
  } = {}) {
    const hours = Math.max(
      0,
      numberOrDefault(
        downtimeHours,
        1
      )
    );
  
    const rate = Math.max(
      0,
      numberOrDefault(
        unitsPerHour,
        48
      )
    );
  
    const value = Math.max(
      0,
      numberOrDefault(
        productValuePerUnit,
        1
      )
    );
  
    const directUnitsLost =
      Math.round(
        rate * hours
      );
  
    const directRevenueImpact =
      directUnitsLost * value;
  
    let urgency = "MODERATE";
  
    if (
      rulDays !== null &&
      Number.isFinite(Number(rulDays))
    ) {
      const days = Number(rulDays);
  
      if (days <= 3) {
        urgency = "CRITICAL";
      } else if (days <= 10) {
        urgency = "HIGH";
      }
    }
  
    return {
      machineId:
        machineId || "UNKNOWN",
      rulDays,
      downtimeHours: hours,
      directUnitsLost,
      directRevenueImpact,
      urgency,
    };
  }
  
  export function compareSchedule({
    baseline = {},
    proposed = {},
  } = {}) {
    const baselineResult =
      simulateProduction(baseline);
  
    const proposedResult =
      simulateProduction(proposed);
  
    return {
      baseline: baselineResult,
      proposed: proposedResult,
      deltaUnits:
        proposedResult.projectedTotalUnits -
        baselineResult.projectedTotalUnits,
      deltaOee:
        proposedResult.estimatedOee -
        baselineResult.estimatedOee,
    };
  }