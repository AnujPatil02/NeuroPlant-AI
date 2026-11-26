import React, { useMemo, useRef } from "react";
import { Html } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";

// ═══════════════════════════════════════════════════════════════════
// Material flow — three production lines feeding shared downstream
// process stations.
// ═══════════════════════════════════════════════════════════════════
// The factory process is deliberately modeled as a manufacturing flow,
// not as a decorative loop:
//
// RAW MATERIAL RECEIVING
//        │
//        ├── LINE 01 → CNC-01 → CNC-02 → CNC-03 → CNC-04 ─┐
//        ├── LINE 02 → CNC-05 → CNC-06 → CNC-07 → CNC-08 ─┼→ PROCESS
//        └── LINE 03 → CNC-09 → CNC-10 → CNC-11 → CNC-12 ─┘  TREATMENT
//                                                               │
//                                            WASH / DEBURR / HEAT
//                                                               │
//                                                         INSPECTION
//                                                               │
//                                                            ASSEMBLY
//                                                               │
//                                                         FINAL QC
//                                                               │
//                                                       FINISHED GOODS
//                                                               │
//                                                            SHIPPING
//
// This means each line has its own inbound/outbound stream. The three
// streams converge only after machining, which is the physically sensible
// relationship for the shared treatment / inspection / assembly stages.

const SHARED_DOWNSTREAM = [
  [7.6, -12], // treatment approach
  [9.0, -12], // treatment exit side
  [9.0, -6],
  [9.0, 0],   // inspection corridor
  [9.0, 6],
  [9.0, 12],  // assembly approach
  [10.5, 12], // assembly exit
  [14.5, 12], // final QC
  [19.5, 12], // finished goods
  [24.5, 12], // loading lane
  [27, 12],   // shipping exit
];

const LINE_ROUTES = [
  {
    id: "LINE-01",
    color: "#6d787f",
    waypoints: [
      [-24, 0],    // common receiving point
      [-24, -8.5], // split to line-01 material aisle
      [-20, -8.5],
      [-18, -8.5],
      [-12, -8.5],
      [-6, -8.5],
      [0, -8.5],
      [3.5, -8.5],
      [6.8, -8.5],
      [6.8, -12],
      ...SHARED_DOWNSTREAM,
    ],
  },
  {
    id: "LINE-02",
    color: "#7a848b",
    waypoints: [
      [-24, 0],    // common receiving point
      [-24, 3.5],  // split to line-02 material aisle
      [-20, 3.5],
      [-18, 3.5],
      [-12, 3.5],
      [-6, 3.5],
      [0, 3.5],
      [3.5, 3.5],
      [6.8, 3.5],
      [6.8, 0],
      [6.8, -6],
      [6.8, -12],
      ...SHARED_DOWNSTREAM,
    ],
  },
  {
    id: "LINE-03",
    color: "#5f6a71",
    waypoints: [
      [-24, 0],    // common receiving point
      [-24, 15.5], // split to line-03 material aisle
      [-20, 15.5],
      [-18, 15.5],
      [-12, 15.5],
      [-6, 15.5],
      [0, 15.5],
      [3.5, 15.5],
      [6.8, 15.5],
      [6.8, 12],
      [6.8, 6],
      [6.8, 0],
      [6.8, -6],
      [6.8, -12],
      ...SHARED_DOWNSTREAM,
    ],
  },
];
function _lerp(a, b, t) {
  return a + (b - a) * t;
}

function buildPathMetrics(waypoints) {
  const lengths = waypoints.slice(0, -1).map((point, i) => {
    const next = waypoints[i + 1];
    return Math.hypot(next[0] - point[0], next[1] - point[1]);
  });

  const cumulative = [0];
  lengths.forEach((length) => {
    cumulative.push(cumulative[cumulative.length - 1] + length);
  });

  return {
    lengths,
    cumulative,
    total: cumulative[cumulative.length - 1],
  };
}

const ROUTE_METRICS = LINE_ROUTES.map((route) => buildPathMetrics(route.waypoints));

function positionOnRoute(routeIndex, progress) {
  const route = LINE_ROUTES[routeIndex];
  const metrics = ROUTE_METRICS[routeIndex];
  const distance = Math.max(0, Math.min(1, progress)) * metrics.total;

  let segmentIndex = metrics.lengths.length - 1;
  for (let i = 0; i < metrics.lengths.length; i += 1) {
    if (distance <= metrics.cumulative[i + 1]) {
      segmentIndex = i;
      break;
    }
  }

  const startDistance = metrics.cumulative[segmentIndex];
  const segmentLength = metrics.lengths[segmentIndex] || 1;
  const t = (distance - startDistance) / segmentLength;
  const [ax, az] = route.waypoints[segmentIndex];
  const [bx, bz] = route.waypoints[segmentIndex + 1];

  return [_lerp(ax, bx, t), _lerp(az, bz, t)];
}

function Pallet({ routeIndex, offset = 0, speed = 0.03, color }) {
  const groupRef = useRef();

  useFrame((state) => {
    if (!groupRef.current) return;

    const elapsed = state.clock.getElapsedTime();
    const progress = (elapsed * speed + offset) % 1;
    const [x, z] = positionOnRoute(routeIndex, progress);

    groupRef.current.position.x = x;
    groupRef.current.position.z = z;

    // Pallets disappear shortly before the shipping boundary so the
    // wrap back to receiving is not visible as a teleport.
    groupRef.current.visible = progress <= 0.975;
  });

  const start = LINE_ROUTES[routeIndex].waypoints[0];

  return (
    <group ref={groupRef} position={[start[0], 0, start[1]]}>
      <mesh position={[0, 0.14, 0]} castShadow receiveShadow>
        <boxGeometry args={[0.82, 0.16, 0.82]} />
        <meshStandardMaterial
          color={color}
          roughness={0.78}
          metalness={0.18}
        />
      </mesh>
      <mesh position={[0, 0.3, 0]} castShadow>
        <cylinderGeometry args={[0.16, 0.16, 0.18, 12]} />
        <meshStandardMaterial
          color="#a2abb0"
          roughness={0.48}
          metalness={0.62}
        />
      </mesh>
    </group>
  );
}

function FlowSystem() {
  const pallets = useMemo(
    () =>
      LINE_ROUTES.flatMap((route, routeIndex) =>
        [0.04, 0.37, 0.70].map((offset, i) => ({
          id: `${route.id}-${i}`,
          routeIndex,
          offset,
          speed: 0.028,
          color: route.color,
        }))
      ),
    []
  );

  return (
    <group>
      {pallets.map((pallet) => (
        <Pallet key={pallet.id} {...pallet} />
      ))}
    </group>
  );
}

function NorthIndicator() {
  return (
    <Html
      position={[27, 0.5, -20]}
      center
      distanceFactor={20}
      style={{ pointerEvents: "none", userSelect: "none" }}
    >
      <div className="scene-orientation">
        <span>N</span>
        <div className="orientation-line" />
      </div>
    </Html>
  );
}

export default function SceneOverlays({
  showFlow = true,
  showOrientation = true,
}) {
  return (
    <group>
      {showFlow && <FlowSystem />}
      {showOrientation && <NorthIndicator />}
    </group>
  );
}
