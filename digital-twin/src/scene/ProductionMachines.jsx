import React, { useMemo, useRef } from "react";
import * as THREE from "three";
import { Html } from "@react-three/drei";
import { deriveMachineStatus } from "../data/twinState";

// ═══════════════════════════════════════════════════════════════════
// Machine layout — a proper 3x4 grid for the 12 CNC centres
// ═══════════════════════════════════════════════════════════════════
// Line 01 (Component Machining)   z = -12
// Line 02 (Precision Machining)   z =   0
// Line 03 (Finishing)             z = +12
//
// Each line has 4 machines at x = -18, -12, -6, 0 -- exactly 6 units
// apart. The shared treatment and assembly assets sit just beyond the CNC
// envelope on the east process spine so they remain visually connected to all lines.
const LINE_Z = {
  "Component Machining": -12,
  "Precision Machining": 0,
  "Finishing / Component Processing": 12,
  "Automated Assembly": 12,
  "Process Treatment": -12,
};

const LINE_X_START = -18;
const MACHINE_SPACING = 6;
// Surface-detail constants for CNC machines. These are the small
// features that read as "real machine" up close: a coolant hose, a
// chip bin below the bed, safety bollards at the corners, a cable
// tray running from the control cabinet to the machine body, and a
// small tool-change station on the side.
const CNC_SURFACE_DETAILS = {
  bollardColor: "#c4a032",
  chipBinColor: "#1a1f24",
  hoseColor: "#1f3a45",
  cableTrayColor: "#2f3a42",
};
const _MACHINE_LINE = {
  "CNC-01": "Component Machining",
  "CNC-02": "Component Machining",
  "CNC-03": "Component Machining",
  "CNC-04": "Component Machining",
  "CNC-05": "Precision Machining",
  "CNC-06": "Precision Machining",
  "CNC-07": "Precision Machining",
  "CNC-08": "Precision Machining",
  "CNC-09": "Finishing / Component Processing",
  "CNC-10": "Finishing / Component Processing",
  "CNC-11": "Finishing / Component Processing",
  "CNC-12": "Finishing / Component Processing",
  "ASM-01": "Automated Assembly",
  "ZONE_TREATMENT": "Process Treatment",
};

// Compute the position for every CNC on its line, in order.
// The 4 CNCs per line are numbered 1-4 within their line.
const _LINE_INDEX = {};
Object.entries(_MACHINE_LINE).forEach(([id, line]) => {
  _LINE_INDEX[line] = _LINE_INDEX[line] || 0;
  // Only assign an index in the 4-slot grid to the CNCs.
  if (id.startsWith("CNC-")) {
    _LINE_INDEX[line] += 1;
    _LINE_INDEX[id] = _LINE_INDEX[line] - 1;
  }
});

// Machines are positioned at y = 0 (ground level). The machine group
// itself contains the base plate at its own local y-offset, so the
// world position is the floor contact point, not the machine center.
const MACHINE_POSITIONS = (() => {
  const positions = {};
  Object.entries(_MACHINE_LINE).forEach(([id, line]) => {
    const z = LINE_Z[line] ?? 0;
    if (id.startsWith("CNC-")) {
      const slot = _LINE_INDEX[id] ?? 0;
      positions[id] = [LINE_X_START + slot * MACHINE_SPACING, 0, z];
    } else if (id === "ZONE_TREATMENT") {
      // Process treatment cell — sits on the east process spine, well
      // clear of the CNC envelope (which ends at x = +1.6). Moving it
      // from x=5.5 to x=12 gives the treatment tunnel enough room to
      // be a proper tunnel rather than a crowded box.
      positions[id] = [12, 0, -12];
    } else if (id === "ASM-01") {
      // Assembly robot cell — aligned with Line 03, east of CNC-12.
      positions[id] = [12, 0, 12];
    } else {
      positions[id] = [0, 0, 0];
    }
  });
  return positions;
})();

const CNC_IDS = Object.keys(MACHINE_POSITIONS).filter((id) =>
  id.startsWith("CNC-")
);

export function getFactoryMachinePosition(machineId) {
  return MACHINE_POSITIONS[machineId] || [0, 1, 0];
}

export function getMachineWorldPosition(machineId) {
  return getFactoryMachinePosition(machineId);
}

// ═══════════════════════════════════════════════════════════════════
// Machine archetypes — three visibly different CNC designs
// ═══════════════════════════════════════════════════════════════════
// The plan's §6 asks for variety without 12 unique models. We use three
// archetypes:
//   A - Turning Centre (CNC-01, 02, 03, 04)
//   B - Vertical Machining Centre (CNC-05, 06, 07, 08)
//   C - 5-Axis Precision Centre (CNC-09, 10, 11, 12)
// The footprint is identical (3.2 x 2.7 m); the design details differ.

const ARCHETYPE_BY_MACHINE = {
  "CNC-01": "A", "CNC-02": "A", "CNC-03": "A", "CNC-04": "A",
  "CNC-05": "B", "CNC-06": "B", "CNC-07": "B", "CNC-08": "B",
  "CNC-09": "C", "CNC-10": "C", "CNC-11": "C", "CNC-12": "C",
};

function statusColor(status) {
  switch (status) {
    case "FAULT":
    case "CRITICAL":
      return "#e45757";
    case "WARNING":
      return "#d59b42";
    case "MAINTENANCE":
      return "#8b78d4";
    case "OFFLINE":
      return "#5f6a72";
    case "IDLE":
      return "#849097";
    case "RUNNING":
    case "ONLINE":
    default:
      return "#72a87c";
  }
}

const WARNING_RING_MACHINES = new Set(["CNC-02", "CNC-07", "CNC-08"]);
const WARNING_RING_COLOR = "#d9a441";

function WarningRing({ machineId }) {
  if (!WARNING_RING_MACHINES.has(machineId)) return null;

  return (
    <>
      <mesh
        position={[0, 0.075, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
      >
        <ringGeometry args={[2.18, 2.31, 48]} />
        <meshBasicMaterial
          color={WARNING_RING_COLOR}
          transparent
          opacity={0.92}
          side={THREE.DoubleSide}
        />
      </mesh>
      <mesh
        position={[0, 0.07, 0]}
        rotation={[-Math.PI / 2, 0, 0]}
      >
        <ringGeometry args={[2.42, 2.48, 48]} />
        <meshBasicMaterial
          color={WARNING_RING_COLOR}
          transparent
          opacity={0.32}
          side={THREE.DoubleSide}
        />
      </mesh>
    </>
  );
}

function StatusBeacon({ status }) {
  const color = statusColor(status);
  const isAlarm = status === "FAULT" || status === "CRITICAL";
  const isWarning = status === "WARNING";

  return (
    <group position={[0, 2.75, 0]}>
      <mesh>
        <cylinderGeometry args={[0.11, 0.11, 0.1, 20]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={isAlarm ? 3.0 : isWarning ? 1.6 : 0.9}
          roughness={0.35}
        />
      </mesh>

      {(isAlarm || isWarning) && (
        <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, -0.05, 0]}>
          <ringGeometry args={[0.2, 0.26, 24]} />
          <meshBasicMaterial
            color={color}
            transparent
            opacity={isAlarm ? 0.7 : 0.45}
            side={THREE.DoubleSide}
          />
        </mesh>
      )}
    </group>
  );
}

function BaseFeet() {
  return (
    <>
      {[
        [-1.3, -1.0],
        [1.3, -1.0],
        [-1.3, 1.0],
        [1.3, 1.0],
      ].map(([x, z], i) => (
        <mesh key={`foot-${i}`} position={[x, 0.1, z]} castShadow>
          <cylinderGeometry args={[0.15, 0.15, 0.2, 12]} />
          <meshStandardMaterial color="#1a2126" roughness={0.6} metalness={0.5} />
        </mesh>
      ))}
    </>
  );
}

// ── Archetype A: Turning Centre ────────────────────────────────────
// Longer spindle housing protruding forward, chip conveyor visible
// underneath. Reads as a lathe / turning centre.
function TurningCentre({ accent, status }) {
  return (
    <>
      {/* Base plinth */}
      <mesh position={[0, 0.35, 0]} castShadow receiveShadow>
        <boxGeometry args={[3.2, 0.7, 2.7]} />
        <meshStandardMaterial color="#252c31" roughness={0.72} metalness={0.42} />
      </mesh>

      {/* Chip conveyor slot */}
      <mesh position={[0, 0.75, -1.35]}>
        <boxGeometry args={[3.0, 0.18, 0.18]} />
        <meshStandardMaterial color="#0d1216" roughness={0.9} metalness={0.2} />
      </mesh>

      {/* Main body — longer in Z to read as turning centre */}
      <mesh position={[0, 1.6, -0.15]} castShadow>
        <boxGeometry args={[2.8, 1.8, 2.4]} />
        <meshStandardMaterial color="#1e2529" roughness={0.66} metalness={0.52} />
      </mesh>

      {/* Front viewing window */}
      <mesh position={[0, 1.7, 1.06]}>
        <boxGeometry args={[1.7, 1.1, 0.06]} />
        <meshStandardMaterial
          color="#0a1014"
          roughness={0.18}
          metalness={0.5}
        />
      </mesh>

      {/* Spindle housing protruding forward */}
      <mesh position={[0, 1.6, 1.25]} rotation={[Math.PI / 2, 0, 0]} castShadow>
        <cylinderGeometry args={[0.28, 0.32, 0.5, 20]} />
        <meshStandardMaterial color="#454e54" roughness={0.38} metalness={0.72} />
      </mesh>

      {/* Tool turret peeking out */}
      <mesh position={[0, 1.35, 1.45]}>
        <cylinderGeometry args={[0.16, 0.16, 0.2, 8]} />
        <meshStandardMaterial color="#6b747a" roughness={0.3} metalness={0.85} />
      </mesh>

      {/* Control panel on a swing arm */}
      <group position={[0.9, 2.15, 0.5]}>
        <mesh position={[-0.35, 0, 0]}>
          <boxGeometry args={[0.55, 0.42, 0.28]} />
          <meshStandardMaterial color="#14191c" roughness={0.6} metalness={0.5} />
        </mesh>
        <mesh position={[-0.35, 0, 0.16]}>
          <boxGeometry args={[0.42, 0.3, 0.03]} />
          <meshStandardMaterial
            color="#0a1014"
            emissive="#26313a"
            emissiveIntensity={0.35}
            roughness={0.25}
          />
        </mesh>
      </group>

      {/* Door handle */}
      <mesh position={[0.95, 1.45, 1.12]}>
        <boxGeometry args={[0.06, 0.7, 0.06]} />
        <meshStandardMaterial color={accent} roughness={0.4} metalness={0.72} />
      </mesh>
    </>
  );
}

// ── Archetype B: Vertical Machining Centre ─────────────────────────
// Taller, wider, with two front access doors and a top-mounted spindle
// bridge. Reads as a VMC.
function VerticalMachiningCentre({ accent, status }) {
  return (
    <>
      {/* Base plinth */}
      <mesh position={[0, 0.35, 0]} castShadow receiveShadow>
        <boxGeometry args={[3.2, 0.7, 2.7]} />
        <meshStandardMaterial color="#252c31" roughness={0.72} metalness={0.42} />
      </mesh>

      {/* Main enclosure — taller */}
      <mesh position={[0, 1.75, 0]} castShadow>
        <boxGeometry args={[2.95, 2.1, 2.35]} />
        <meshStandardMaterial color="#1d242a" roughness={0.68} metalness={0.5} />
      </mesh>

      {/* Top-mounted spindle bridge */}
      <mesh position={[0, 2.95, 0]} castShadow>
        <boxGeometry args={[1.4, 0.35, 1.6]} />
        <meshStandardMaterial color="#171d22" roughness={0.6} metalness={0.55} />
      </mesh>

      {/* Two front doors, side by side */}
      <mesh position={[-0.7, 1.75, 1.19]}>
        <boxGeometry args={[1.2, 1.55, 0.06]} />
        <meshStandardMaterial
          color="#0a1014"
          roughness={0.2}
          metalness={0.5}
        />
      </mesh>
      <mesh position={[0.7, 1.75, 1.19]}>
        <boxGeometry args={[1.2, 1.55, 0.06]} />
        <meshStandardMaterial
          color="#0a1014"
          roughness={0.2}
          metalness={0.5}
        />
      </mesh>

      {/* Door seam */}
      <mesh position={[0, 1.75, 1.21]}>
        <boxGeometry args={[0.04, 1.55, 0.02]} />
        <meshStandardMaterial color="#3a4348" roughness={0.5} metalness={0.5} />
      </mesh>

      {/* Two door handles */}
      <mesh position={[0.28, 1.35, 1.24]}>
        <boxGeometry args={[0.05, 0.5, 0.05]} />
        <meshStandardMaterial color={accent} roughness={0.4} metalness={0.72} />
      </mesh>
      <mesh position={[-0.28, 1.35, 1.24]}>
        <boxGeometry args={[0.05, 0.5, 0.05]} />
        <meshStandardMaterial color={accent} roughness={0.4} metalness={0.72} />
      </mesh>

      {/* Side control cabinet */}
      <mesh position={[1.7, 1.55, -0.2]} castShadow>
        <boxGeometry args={[0.5, 1.9, 1.3]} />
        <meshStandardMaterial color="#1a2024" roughness={0.62} metalness={0.48} />
      </mesh>
      <mesh position={[1.96, 1.7, -0.2]}>
        <boxGeometry args={[0.03, 0.5, 0.6]} />
        <meshStandardMaterial
          color="#0a1014"
          emissive="#2d3841"
          emissiveIntensity={0.4}
          roughness={0.25}
        />
      </mesh>
    </>
  );
}

// ── Archetype C: 5-Axis Precision Centre ───────────────────────────
// Sloped front hood, rounded top, larger viewing aperture. Reads as a
// high-end 5-axis milling machine.
function FiveAxisCentre({ accent, status }) {
  return (
    <>
      {/* Base plinth */}
      <mesh position={[0, 0.35, 0]} castShadow receiveShadow>
        <boxGeometry args={[3.2, 0.7, 2.7]} />
        <meshStandardMaterial color="#252c31" roughness={0.72} metalness={0.42} />
      </mesh>

      {/* Main enclosure — larger viewing aperture on top */}
      <mesh position={[0, 1.8, 0]} castShadow>
        <boxGeometry args={[2.85, 2.2, 2.4]} />
        <meshStandardMaterial color="#1b2227" roughness={0.62} metalness={0.55} />
      </mesh>

      {/* Rounded top hood */}
      <mesh position={[0, 3.0, 0]} rotation={[0, 0, 0]} castShadow>
        <boxGeometry args={[2.85, 0.35, 2.4]} />
        <meshStandardMaterial color="#141a1f" roughness={0.55} metalness={0.6} />
      </mesh>

      {/* Large front viewing window (taller aperture) */}
      <mesh position={[0, 1.9, 1.22]}>
        <boxGeometry args={[2.1, 1.6, 0.06]} />
        <meshStandardMaterial
          color="#0a1014"
          roughness={0.15}
          metalness={0.55}
        />
      </mesh>

      {/* Window frame highlight */}
      <mesh position={[0, 1.9, 1.25]}>
        <boxGeometry args={[2.16, 1.66, 0.01]} />
        <meshStandardMaterial
          color={accent}
          transparent
          opacity={0.15}
          roughness={0.3}
          metalness={0.7}
        />
      </mesh>

      {/* Side panel with ventilation grille */}
      <mesh position={[-1.47, 1.8, 0]}>
        <boxGeometry args={[0.05, 1.4, 1.8]} />
        <meshStandardMaterial color="#10161b" roughness={0.7} metalness={0.4} />
      </mesh>

      {/* Two small vents on the side */}
      {[0.4, -0.4].map((z, i) => (
        <mesh key={`vent-${i}`} position={[-1.5, 1.4, z]}>
          <boxGeometry args={[0.02, 0.5, 0.7]} />
          <meshStandardMaterial color="#0a0f12" roughness={0.95} metalness={0.1} />
        </mesh>
      ))}

      {/* Integrated control panel */}
      <mesh position={[1.55, 1.85, 0.3]} castShadow>
        <boxGeometry args={[0.35, 0.75, 0.7]} />
        <meshStandardMaterial color="#141a1e" roughness={0.58} metalness={0.5} />
      </mesh>
      <mesh position={[1.74, 2.0, 0.3]}>
        <boxGeometry args={[0.03, 0.45, 0.5]} />
        <meshStandardMaterial
          color="#0a1014"
          emissive="#355058"
          emissiveIntensity={0.55}
          roughness={0.22}
        />
      </mesh>

      {/* Door handle */}
      <mesh position={[1.1, 1.5, 1.25]}>
        <boxGeometry args={[0.06, 0.8, 0.06]} />
        <meshStandardMaterial color={accent} roughness={0.4} metalness={0.72} />
      </mesh>
    </>
  );
}

// ── CNC surface details ───────────────────────────────────────────
// Small procedural features that make the CNC machines read as real
// industrial equipment rather than abstract boxes. Everything is
// rendered inside the machine's local coordinate space, so it moves
// with the machine.

function SafetyBollards({ corners = true }) {
  // Four short yellow bollards at the corners of the machine footprint
  const positions = corners
    ? [[-1.85, -1.55], [1.85, -1.55], [-1.85, 1.55], [1.85, 1.55]]
    : [];
  return (
    <group>
      {positions.map(([x, z], i) => (
        <group key={`bollard-${i}`} position={[x, 0, z]}>
          <mesh position={[0, 0.35, 0]} castShadow>
            <cylinderGeometry args={[0.09, 0.09, 0.7, 12]} />
            <meshStandardMaterial
              color={CNC_SURFACE_DETAILS.bollardColor}
              roughness={0.55}
              metalness={0.5}
            />
          </mesh>
          {/* Yellow reflective band */}
          <mesh position={[0, 0.55, 0]}>
            <cylinderGeometry args={[0.095, 0.095, 0.1, 12]} />
            <meshStandardMaterial
              color="#f0c14a"
              emissive="#b58b1a"
              emissiveIntensity={0.3}
              roughness={0.5}
            />
          </mesh>
        </group>
      ))}
    </group>
  );
}

function ChipBin() {
  // A shallow chip/coolant recovery bin positioned under the front of
  // the machine. Reads as the "swarf tray" that real CNCs have.
  return (
    <group position={[0, 0.08, 1.55]}>
      {/* Bin body */}
      <mesh castShadow receiveShadow>
        <boxGeometry args={[1.4, 0.16, 0.5]} />
        <meshStandardMaterial
          color={CNC_SURFACE_DETAILS.chipBinColor}
          roughness={0.85}
          metalness={0.3}
        />
      </mesh>
      {/* Metal swarf visible in the tray */}
      <mesh position={[0, 0.09, 0]}>
        <boxGeometry args={[1.2, 0.03, 0.35]} />
        <meshStandardMaterial
          color="#7a8188"
          roughness={0.55}
          metalness={0.75}
        />
      </mesh>
    </group>
  );
}

function CoolantHose({ side = "left" }) {
  // A short coolant hose that runs from the base of the machine to the
  // coolant unit at the back. Rendered as a thin dark cylinder with a
  // metallic connector at each end.
  const x = side === "left" ? -1.5 : 1.5;
  return (
    <group position={[x, 0.5, -1.15]}>
      {/* Hose body */}
      <mesh rotation={[0, 0, 0.2]} castShadow>
        <cylinderGeometry args={[0.05, 0.05, 0.9, 10]} />
        <meshStandardMaterial
          color={CNC_SURFACE_DETAILS.hoseColor}
          roughness={0.75}
          metalness={0.2}
        />
      </mesh>
      {/* Metal connector at base */}
      <mesh position={[0, -0.5, 0]}>
        <cylinderGeometry args={[0.08, 0.08, 0.12, 10]} />
        <meshStandardMaterial
          color="#6a737a"
          roughness={0.4}
          metalness={0.8}
        />
      </mesh>
    </group>
  );
}

function CableTray() {
  // A short cable tray running from the control cabinet down to the
  // machine base. Rendered as a thin channel with visible "cables" as
  // narrower cylinders inside.
  return (
    <group position={[1.45, 1.9, -0.2]}>
      {/* Tray body */}
      <mesh castShadow>
        <boxGeometry args={[0.15, 0.85, 0.6]} />
        <meshStandardMaterial
          color={CNC_SURFACE_DETAILS.cableTrayColor}
          roughness={0.7}
          metalness={0.55}
        />
      </mesh>
      {/* Visible cables inside */}
      {[-0.15, 0, 0.15].map((offset, i) => (
        <mesh key={`cable-${i}`} position={[0.09, 0, offset]} rotation={[0, 0, Math.PI / 2]}>
          <cylinderGeometry args={[0.02, 0.02, 0.8, 8]} />
          <meshStandardMaterial
            color={i === 0 ? "#a83e3e" : i === 1 ? "#3e5a8a" : "#2a2a2a"}
            roughness={0.85}
          />
        </mesh>
      ))}
    </group>
  );
}

function MachineSurfaceDetails() {
  return (
    <>
      <SafetyBollards />
      <ChipBin />
      <CoolantHose side="left" />
      <CoolantHose side="right" />
      <CableTray />
    </>
  );
}

function CNCMachine({ machine, selected, onSelect }) {
  const groupRef = useRef();
  const status = deriveMachineStatus(machine);

  const accent = selected ? "#d8dde0" : "#707b82";
  const archetype = ARCHETYPE_BY_MACHINE[machine.machineId] || "A";

  let MachineBody;
  switch (archetype) {
    case "B":
      MachineBody = VerticalMachiningCentre;
      break;
    case "C":
      MachineBody = FiveAxisCentre;
      break;
    case "A":
    default:
      MachineBody = TurningCentre;
  }

  return (
    <group
      ref={groupRef}
      position={getFactoryMachinePosition(machine.machineId)}
      onClick={(event) => {
        event.stopPropagation();
        onSelect(machine.machineId);
      }}
      onPointerOver={() => {
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => {
        document.body.style.cursor = "default";
      }}
    >
            <BaseFeet />

{/* Flush machine foundation pad — keeps the CNC visually seated on
    the factory slab instead of appearing to float above it. */}
<mesh position={[0, 0.025, 0]} receiveShadow>
  <boxGeometry args={[3.35, 0.05, 2.85]} />
  <meshStandardMaterial
    color="#1b2227"
    roughness={0.9}
    metalness={0.18}
  />
</mesh>

{/* Procedural surface details (bollards, chip bin, hoses, cable tray) */}
<MachineSurfaceDetails />

<MachineBody accent={accent} status={status} />
      <StatusBeacon status={status} />
      <WarningRing machineId={machine.machineId} />

      {/* Selection indicator — subtle floor ring, not a wireframe cage */}
      {selected && (
        <>
          <mesh
            position={[0, 0.06, 0]}
            rotation={[-Math.PI / 2, 0, 0]}
          >
            <ringGeometry args={[2.2, 2.35, 48]} />
            <meshBasicMaterial
              color="#d8dde0"
              transparent
              opacity={0.9}
              side={THREE.DoubleSide}
            />
          </mesh>
          <mesh
            position={[0, 0.055, 0]}
            rotation={[-Math.PI / 2, 0, 0]}
          >
            <ringGeometry args={[2.45, 2.52, 48]} />
            <meshBasicMaterial
              color="#d8dde0"
              transparent
              opacity={0.35}
              side={THREE.DoubleSide}
            />
          </mesh>
        </>
      )}

      {/* Machine label */}
      <Html
        position={[0, 3.6, 0]}
        center
        distanceFactor={16}
        style={{
          pointerEvents: "none",
          userSelect: "none",
        }}
      >
        <div className={`machine-world-label ${selected ? "selected" : ""}`}>
          <span>{machine.machineId}</span>
          <small>{status}</small>
        </div>
      </Html>
    </group>
  );
}

// ── Support assets ───────────────────────────────────────────────
// ZONE_TREATMENT and ASM-01 are visually distinct from the CNCs.
// ZONE_TREATMENT renders as a process tunnel; ASM-01 renders as an
// assembly robot cell. Both dispatch through the same
// SupportMachine wrapper so the selection highlight, status beacon,
// and HTML label work identically.

function ProcessTreatmentTunnel({ status }) {
  const beaconColor = statusColor(status);

  // Material flow visual language: the tunnel is a rectangular shell
  // with an inlet opening on the west face and an outlet opening on
  // the east face. A short conveyor runs through the middle.
  return (
    <group>
      {/* Main tunnel shell */}
      <mesh position={[0, 1.4, 0]} castShadow receiveShadow>
        <boxGeometry args={[5.5, 2.8, 3.2]} />
        <meshStandardMaterial
          color="#2a333a"
          roughness={0.72}
          metalness={0.42}
        />
      </mesh>

      {/* Inlet opening — dark recess on the west face */}
      <mesh position={[-2.76, 1.0, 0]} rotation={[0, -Math.PI / 2, 0]}>
        <planeGeometry args={[1.6, 1.2]} />
        <meshBasicMaterial color="#05080a" />
      </mesh>

      {/* Outlet opening — dark recess on the east face */}
      <mesh position={[2.76, 1.0, 0]} rotation={[0, Math.PI / 2, 0]}>
        <planeGeometry args={[1.6, 1.2]} />
        <meshBasicMaterial color="#05080a" />
      </mesh>

      {/* Conveyor running through the tunnel */}
      <mesh position={[0, 0.32, 0]} castShadow>
        <boxGeometry args={[6.2, 0.18, 0.9]} />
        <meshStandardMaterial
          color="#3d4750"
          roughness={0.7}
          metalness={0.55}
        />
      </mesh>

      {/* Conveyor rollers visible as small cylinders at the ends */}
      {[-3.0, 3.0].map((x, i) => (
        <mesh
          key={`roller-${i}`}
          position={[x, 0.32, 0]}
          rotation={[0, 0, Math.PI / 2]}
        >
          <cylinderGeometry args={[0.14, 0.14, 0.9, 12]} />
          <meshStandardMaterial
            color="#5a646c"
            roughness={0.5}
            metalness={0.75}
          />
        </mesh>
      ))}

      {/* Heat-treatment chimney at the top */}
      <mesh position={[0, 3.2, -0.6]} castShadow>
        <cylinderGeometry args={[0.4, 0.45, 1.2, 16]} />
        <meshStandardMaterial
          color="#4a555c"
          roughness={0.6}
          metalness={0.65}
        />
      </mesh>

      {/* Chimney cap */}
      <mesh position={[0, 3.85, -0.6]}>
        <cylinderGeometry args={[0.55, 0.5, 0.1, 16]} />
        <meshStandardMaterial
          color="#39434a"
          roughness={0.55}
          metalness={0.7}
        />
      </mesh>

      {/* Rooftop vent box */}
      <mesh position={[1.6, 3.05, 0.6]} castShadow>
        <boxGeometry args={[1.0, 0.5, 1.0]} />
        <meshStandardMaterial
          color="#1e262c"
          roughness={0.65}
          metalness={0.5}
        />
      </mesh>

      {/* Control cabinet on the side */}
      <mesh position={[0, 1.35, 1.85]} castShadow>
        <boxGeometry args={[1.6, 1.8, 0.5]} />
        <meshStandardMaterial
          color="#1e242a"
          roughness={0.62}
          metalness={0.48}
        />
      </mesh>
      {/* Cabinet display */}
      <mesh position={[0, 1.6, 2.12]}>
        <boxGeometry args={[0.55, 0.4, 0.02]} />
        <meshStandardMaterial
          color="#0a1014"
          emissive="#2d3841"
          emissiveIntensity={0.45}
          roughness={0.26}
        />
      </mesh>

      {/* Status beacon */}
      <mesh position={[0, 3.95, 0.9]}>
        <cylinderGeometry args={[0.1, 0.1, 0.12, 20]} />
        <meshStandardMaterial
          color={beaconColor}
          emissive={beaconColor}
          emissiveIntensity={0.9}
          roughness={0.35}
        />
      </mesh>

      {/* Warning stripes on the west face of the tunnel */}
      {[-1.3, -0.65, 0, 0.65, 1.3].map((z, i) => (
        <mesh
          key={`stripe-${i}`}
          position={[-2.77, 2.6, z]}
          rotation={[0, -Math.PI / 2, 0]}
        >
          <planeGeometry args={[0.3, 0.4]} />
          <meshBasicMaterial color="#b58b32" />
        </mesh>
      ))}
    </group>
  );
}

function AssemblyRobotCell({ status }) {
  const beaconColor = statusColor(status);

  return (
    <group>
      {/* Cell base plinth */}
      <mesh position={[0, 0.15, 0]} castShadow receiveShadow>
        <boxGeometry args={[4.2, 0.3, 4.2]} />
        <meshStandardMaterial
          color="#262d33"
          roughness={0.82}
          metalness={0.3}
        />
      </mesh>

      {/* Safety cage — four corner posts + top frame */}
      {[
        [-1.9, -1.9], [1.9, -1.9], [-1.9, 1.9], [1.9, 1.9],
      ].map(([x, z], i) => (
        <mesh key={`cage-post-${i}`} position={[x, 1.5, z]} castShadow>
          <boxGeometry args={[0.12, 2.7, 0.12]} />
          <meshStandardMaterial
            color={CNC_SURFACE_DETAILS.bollardColor}
            roughness={0.6}
            metalness={0.5}
          />
        </mesh>
      ))}

      {/* Top frame rails */}
      {[[-1.9, 0], [1.9, 0]].map(([x, z], i) => (
        <mesh key={`top-rail-x-${i}`} position={[x, 2.85, z]}>
          <boxGeometry args={[0.1, 0.1, 3.9]} />
          <meshStandardMaterial
            color={CNC_SURFACE_DETAILS.bollardColor}
            roughness={0.6}
            metalness={0.5}
          />
        </mesh>
      ))}
      {[[0, -1.9], [0, 1.9]].map(([x, z], i) => (
        <mesh key={`top-rail-z-${i}`} position={[x, 2.85, z]}>
          <boxGeometry args={[3.9, 0.1, 0.1]} />
          <meshStandardMaterial
            color={CNC_SURFACE_DETAILS.bollardColor}
            roughness={0.6}
            metalness={0.5}
          />
        </mesh>
      ))}

      {/* Robot arm base */}
      <mesh position={[0, 0.65, 0]} castShadow>
        <cylinderGeometry args={[0.65, 0.75, 0.7, 20]} />
        <meshStandardMaterial
          color="#3a434b"
          roughness={0.55}
          metalness={0.62}
        />
      </mesh>

      {/* Robot arm — first segment (vertical) */}
      <mesh position={[0, 1.6, 0]} castShadow>
        <boxGeometry args={[0.4, 1.4, 0.4]} />
        <meshStandardMaterial
          color="#e0a730"
          roughness={0.5}
          metalness={0.55}
        />
      </mesh>

      {/* Robot arm — elbow joint */}
      <mesh position={[0, 2.35, 0]} rotation={[Math.PI / 2, 0, 0]} castShadow>
        <cylinderGeometry args={[0.28, 0.28, 0.45, 16]} />
        <meshStandardMaterial
          color="#4a555c"
          roughness={0.42}
          metalness={0.7}
        />
      </mesh>

      {/* Robot arm — second segment (angled forward-down) */}
      <mesh
        position={[0, 2.55, 0.75]}
        rotation={[-Math.PI / 4, 0, 0]}
        castShadow
      >
        <boxGeometry args={[0.32, 1.4, 0.32]} />
        <meshStandardMaterial
          color="#e0a730"
          roughness={0.5}
          metalness={0.55}
        />
      </mesh>

      {/* End effector / gripper at the tip */}
      <mesh position={[0, 2.05, 1.55]} castShadow>
        <boxGeometry args={[0.35, 0.35, 0.35]} />
        <meshStandardMaterial
          color="#2f3a42"
          roughness={0.55}
          metalness={0.65}
        />
      </mesh>

      {/* Assembly table inside the cage */}
      <mesh position={[0, 0.7, 1.55]} castShadow receiveShadow>
        <boxGeometry args={[1.4, 0.08, 0.9]} />
        <meshStandardMaterial
          color="#4a555c"
          roughness={0.68}
          metalness={0.55}
        />
      </mesh>
      {/* Table legs */}
      {[[-0.6, -0.35], [0.6, -0.35], [-0.6, 0.35], [0.6, 0.35]].map(([x, z], i) => (
        <mesh key={`table-leg-${i}`} position={[x, 0.36, 1.55 + z]}>
          <boxGeometry args={[0.08, 0.65, 0.08]} />
          <meshStandardMaterial
            color="#303a41"
            roughness={0.7}
            metalness={0.55}
          />
        </mesh>
      ))}

      {/* Component to be assembled on the table */}
      <mesh position={[0, 0.85, 1.55]}>
        <cylinderGeometry args={[0.18, 0.18, 0.15, 12]} />
        <meshStandardMaterial
          color="#9aa3a8"
          roughness={0.5}
          metalness={0.62}
        />
      </mesh>

      {/* Status beacon */}
      <mesh position={[0, 3.1, 0]}>
        <cylinderGeometry args={[0.1, 0.1, 0.12, 20]} />
        <meshStandardMaterial
          color={beaconColor}
          emissive={beaconColor}
          emissiveIntensity={0.9}
          roughness={0.35}
        />
      </mesh>
    </group>
  );
}

function SupportMachine({ machine, selected, onSelect }) {
  const status = deriveMachineStatus(machine);
  const isTreatment = machine.machineId === "ZONE_TREATMENT";

  // Label position: the treatment tunnel is ~4 units tall, the robot
  // cell ~3.2 units tall. Labels sit slightly above each.
  const labelY = isTreatment ? 4.4 : 3.6;

  return (
    <group
      position={getFactoryMachinePosition(machine.machineId)}
      onClick={(event) => {
        event.stopPropagation();
        onSelect(machine.machineId);
      }}
      onPointerOver={() => {
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => {
        document.body.style.cursor = "default";
      }}
    >
      {isTreatment ? (
        <ProcessTreatmentTunnel status={status} />
      ) : (
        <AssemblyRobotCell status={status} />
      )}

      {/* Selection indicator — floor ring */}
      {selected && (
        <mesh
          position={[0, 0.06, 0]}
          rotation={[-Math.PI / 2, 0, 0]}
        >
          <ringGeometry
            args={isTreatment ? [3.0, 3.15, 48] : [2.3, 2.45, 48]}
          />
          <meshBasicMaterial
            color="#d8dde0"
            transparent
            opacity={0.9}
            side={THREE.DoubleSide}
          />
        </mesh>
      )}

      <Html
        position={[0, labelY, 0]}
        center
        distanceFactor={16}
        style={{ pointerEvents: "none" }}
      >
        <div className={`machine-world-label ${selected ? "selected" : ""}`}>
          <span>{machine.machineId}</span>
          <small>{status}</small>
        </div>
      </Html>
    </group>
  );
}

export default function ProductionMachines({
  machines = {},
  selectedMachineId,
  onSelect,
}) {
  // Only render machines whose IDs we know a position for. This filters
  // out any OPC-UA infrastructure nodes that leaked through (they're
  // also filtered in twinState.js, but belt-and-suspenders here).
  const machineList = useMemo(() => {
    return Object.values(machines || {}).filter((machine) => {
      if (!machine?.machineId) return false;
      return Boolean(MACHINE_POSITIONS[machine.machineId]);
    });
  }, [machines]);

  // Fallback for the very first frame before /twin/machines has returned.
  // Only includes CNC machines so the scene isn't empty.
  const fallbackMachines = useMemo(() => {
    return CNC_IDS.map((machineId) => ({
      machineId,
      operatingMode: "RUNNING",
      maintenanceStatus: "NORMAL",
      productionCount: 0,
      temperature: 45,
      vibration: 2.5,
      rpm: 2800,
      currentDraw: 10,
      pressure: 4.5,
      humidity: 50,
      oee: null,
      rulDays: null,
    }));
  }, []);

  const renderMachines = machineList.length ? machineList : fallbackMachines;

  return (
    <group>
      {renderMachines.map((machine) => {
        const isCNC = machine.machineId.startsWith("CNC-");

        return isCNC ? (
          <CNCMachine
            key={machine.machineId}
            machine={machine}
            selected={selectedMachineId === machine.machineId}
            onSelect={onSelect}
          />
        ) : (
          <SupportMachine
            key={machine.machineId}
            machine={machine}
            selected={selectedMachineId === machine.machineId}
            onSelect={onSelect}
          />
        );
      })}
    </group>
  );
}