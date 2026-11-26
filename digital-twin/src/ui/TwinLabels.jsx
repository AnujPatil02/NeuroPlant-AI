import React from "react";
import { Html } from "@react-three/drei";

// ═══════════════════════════════════════════════════════════════════
// Factory zone labels
// ═══════════════════════════════════════════════════════════════════
// Positions are derived from the machine layout in ProductionMachines.jsx:
//   CNC lines at z = -12, 0, +12; machines span x = -18..0
//   ZONE_TREATMENT at (x=10, z=-12)
//   ASM-01         at (x=10, z=+12)
//
// Floor bounds (from FactoryEnvironment.jsx):
//   x: -26 to +21
//   z: -23 to +23
//
// Every label hovers directly over the physical region it names, not
// floating outside the hall or on top of a machine.

const LABELS = [
  {
    id: "receiving",
    title: "RECEIVING",
    subtitle: "RAW MATERIAL INBOUND",
    // West end of the hall, ahead of Line 01's first machine
    position: [-22, 5.5, -18],
  },
  {
    id: "storage",
    title: "RAW MATERIAL",
    subtitle: "BUFFER / STORAGE",
    // Same west area, offset to avoid overlapping Receiving
    position: [-22, 5.5, -8],
  },
  {
    id: "line01",
    title: "LINE 01",
    subtitle: "COMPONENT MACHINING",
    // Above Line 01, centered over its CNC footprint
    position: [-9, 5.5, -12],
  },
  {
    id: "line02",
    title: "LINE 02",
    subtitle: "PRECISION MACHINING",
    position: [-9, 5.5, 0],
  },
  {
    id: "line03",
    title: "LINE 03",
    subtitle: "FINISHING / PROCESSING",
    position: [-9, 5.5, 12],
  },
  {
    id: "treatment",
    title: "ZONE_TREATMENT",
    subtitle: "WASH / DEBURR / HEAT",
    // Directly above the treatment asset
    position: [10, 5.5, -18],
  },
  {
    id: "assembly",
    title: "ASSEMBLY",
    subtitle: "COMPONENT INTEGRATION",
    // Directly above the ASM-01 robot
    position: [10, 5.5, 18],
  },
  {
    id: "quality",
    title: "QUALITY",
    subtitle: "METROLOGY / INSPECTION",
    // Between assembly and shipping, on the eastern side
    position: [17, 5.5, 12],
  },
  {
    id: "shipping",
    title: "SHIPPING",
    subtitle: "FINISHED GOODS OUTBOUND",
    // East end of the hall
    position: [18, 5.5, 0],
  },
];

function ZoneLabel({ label }) {
  return (
    <Html
      position={label.position}
      center
      distanceFactor={22}
      style={{
        pointerEvents: "none",
        userSelect: "none",
      }}
    >
      <div className="factory-zone-label">
        <div className="factory-zone-label-line" />

        <div className="factory-zone-label-copy">
          <strong>{label.title}</strong>
          <span>{label.subtitle}</span>
        </div>
      </div>
    </Html>
  );
}

export default function TwinLabels({ visible = true }) {
  if (!visible) {
    return null;
  }

  return (
    <group>
      {LABELS.map((label) => (
        <ZoneLabel key={label.id} label={label} />
      ))}
    </group>
  );
}