import React, { useMemo } from "react";
import * as THREE from "three";
const MACHINE_MIN_X = -18;
const MACHINE_MAX_X = 23;   // east logistics / finished-goods / shipping zone
const MACHINE_MIN_Z = -15;  // -12 for CNCs, -3 for machine depth
const MACHINE_MAX_Z = 15;

const FLOOR_MARGIN = 8;
const HALL_MIN_X = MACHINE_MIN_X - FLOOR_MARGIN;   // -26
const HALL_MAX_X = MACHINE_MAX_X + FLOOR_MARGIN;   // +31
const HALL_MIN_Z = MACHINE_MIN_Z - FLOOR_MARGIN;   // -23
const HALL_MAX_Z = MACHINE_MAX_Z + FLOOR_MARGIN;   // +23

const HALL_WIDTH = HALL_MAX_X - HALL_MIN_X;        // 57
const HALL_DEPTH = HALL_MAX_Z - HALL_MIN_Z;        // 46
const HALL_CENTER_X = (HALL_MIN_X + HALL_MAX_X) / 2;   // 2.5
const HALL_CENTER_Z = (HALL_MIN_Z + HALL_MAX_Z) / 2;   // 0

const PILLAR_HEIGHT = 11;
const BEAM_HEIGHT = 0.5;

// Pillars run at two z-rows bracketing the machine envelope.
const PILLAR_ROWS_Z = [HALL_MIN_Z + 0.5, HALL_MAX_Z - 0.5];

// Pillar x-positions: enough pillars to support the beam, but no more
// than necessary. 5 pillars spaced across the hall width.
const PILLAR_COUNT_X = 5;
const PILLAR_SPACING_X = HALL_WIDTH / (PILLAR_COUNT_X - 1);

function _pillarXPositions() {
  const result = [];
  for (let i = 0; i < PILLAR_COUNT_X; i++) {
    result.push(HALL_MIN_X + i * PILLAR_SPACING_X);
  }
  return result;
}

// Light bar x-positions. These are the same x-values the transverse
// beams must be placed at, so the hanger rods (below) attach to real
// geometry instead of floating under empty air.
// Three columns: west (x = -12), middle (x = 2), east (x = 16).
const LIGHT_COLUMN_X = [-12, 2, 16];

function Floor() {
  const concreteJointX = [-24, -18, -12, -6, 0, 6, 12, 18, 24];
  const concreteJointZ = [-18, -12, -6, 0, 6, 12, 18];

  return (
    <group>
      {/* Real factory slab — continuous concrete floor with a proper raised
          structural edge. The machine bases and logistics area share this
          exact datum, so nothing visually floats above a separate plane. */}
      <mesh position={[HALL_CENTER_X, -0.18, HALL_CENTER_Z]} receiveShadow>
        <boxGeometry args={[HALL_WIDTH, 0.36, HALL_DEPTH]} />
        <meshStandardMaterial
          color="#252d32"
          roughness={0.92}
          metalness={0.035}
        />
      </mesh>

      {/* Slightly darker slab perimeter / foundation edge. */}
      <mesh position={[HALL_CENTER_X, -0.015, HALL_MIN_Z + 0.16]} receiveShadow>
        <boxGeometry args={[HALL_WIDTH - 0.35, 0.035, 0.16]} />
        <meshStandardMaterial color="#1a2025" roughness={0.96} metalness={0.02} />
      </mesh>
      <mesh position={[HALL_CENTER_X, -0.015, HALL_MAX_Z - 0.16]} receiveShadow>
        <boxGeometry args={[HALL_WIDTH - 0.35, 0.035, 0.16]} />
        <meshStandardMaterial color="#1a2025" roughness={0.96} metalness={0.02} />
      </mesh>

      {/* Concrete expansion / construction joints. These make the slab read
          as an industrial floor rather than a single dark game surface. */}
      {concreteJointX.map((x) => (
        <mesh
          key={`floor-joint-x-${x}`}
          position={[x, 0.006, 0]}
          rotation={[-Math.PI / 2, 0, 0]}
        >
          <planeGeometry args={[0.045, HALL_DEPTH - 0.5]} />
          <meshBasicMaterial color="#171e23" transparent opacity={0.7} />
        </mesh>
      ))}
      {concreteJointZ.map((z) => (
        <mesh
          key={`floor-joint-z-${z}`}
          position={[0, 0.006, z]}
          rotation={[-Math.PI / 2, 0, 0]}
        >
          <planeGeometry args={[HALL_WIDTH - 0.5, 0.045]} />
          <meshBasicMaterial color="#171e23" transparent opacity={0.7} />
        </mesh>
      ))}

      {/* Three real material-transfer aisles. They run beside the CNC cells,
          not through the machine geometry. */}
      {[-8.5, 3.5, 15.5].map((z, i) => (
        <mesh
          key={`material-aisle-${i}`}
          position={[-9, 0.009, z]}
          rotation={[-Math.PI / 2, 0, 0]}
        >
          <planeGeometry args={[25, 1.05]} />
          <meshStandardMaterial
            color="#303a3e"
            roughness={0.9}
            metalness={0.04}
          />
        </mesh>
      ))}

      {/* Main east-west material transfer aisle immediately beyond the CNC
          envelope. This is the discharge spine used by all three lines. */}
      <mesh position={[3.8, 0.01, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[0.14, 38]} />
        <meshBasicMaterial color="#6d7774" transparent opacity={0.65} />
      </mesh>

      {/* Each line has a dedicated discharge strip at the end of its
          material aisle before the common transfer spine. */}
      {[-8.5, 3.5, 15.5].map((z) => (
        <mesh
          key={`discharge-${z}`}
          position={[3.8, 0.014, z]}
          rotation={[-Math.PI / 2, 0, 0]}
        >
          <planeGeometry args={[5.2, 0.16]} />
          <meshBasicMaterial color="#7b817d" transparent opacity={0.72} />
        </mesh>
      ))}

      {/* Shared process corridor — treatment at the south end, assembly at
          the north end, with inspection and finished goods on the east. */}
      <mesh position={[7.6, 0.012, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[0.14, 36]} />
        <meshBasicMaterial color="#59635f" transparent opacity={0.66} />
      </mesh>

      {/* Treatment approach / exit lanes. */}
      <mesh position={[7.6, 0.013, -12]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[4.4, 0.12]} />
        <meshBasicMaterial color="#737b77" transparent opacity={0.7} />
      </mesh>
      <mesh position={[7.6, 0.013, 12]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[4.4, 0.12]} />
        <meshBasicMaterial color="#737b77" transparent opacity={0.7} />
      </mesh>

      {/* Downstream production spine from assembly to inspection, finished
          goods and shipping. */}
      <mesh position={[16.5, 0.014, 12]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[18, 0.18]} />
        <meshBasicMaterial color="#5c6663" transparent opacity={0.68} />
      </mesh>

      {/* Quality / finished-goods zones are actual floor areas rather than
          floating decorative rectangles. */}
      <mesh position={[14.5, 0.016, 12]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[4.0, 6.0]} />
        <meshBasicMaterial color="#303b3e" transparent opacity={0.58} />
      </mesh>
      <mesh position={[19.5, 0.016, 12]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[6.5, 7.5]} />
        <meshBasicMaterial color="#303a3e" transparent opacity={0.62} />
      </mesh>
      <mesh position={[25, 0.016, 12]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[4.0, 7.5]} />
        <meshBasicMaterial color="#283337" transparent opacity={0.7} />
      </mesh>

      {/* Yellow/black safety border around the finished-goods staging area. */}
      {[
        [19.5, 8.0, 7.5, 0.08],
        [19.5, 16.0, 7.5, 0.08],
      ].map(([x, z, width, depth], i) => (
        <mesh
          key={`fg-safety-${i}`}
          position={[x, 0.022, z]}
          rotation={[-Math.PI / 2, 0, 0]}
        >
          <planeGeometry args={[width, depth]} />
          <meshBasicMaterial color="#b58b32" transparent opacity={0.72} />
        </mesh>
      ))}

      {/* Loading / shipping lane markings. */}
      <mesh position={[25.5, 0.022, 9]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[0.08, 6.0]} />
        <meshBasicMaterial color="#d2a843" transparent opacity={0.8} />
      </mesh>
      <mesh position={[25.5, 0.022, 15]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[0.08, 6.0]} />
        <meshBasicMaterial color="#d2a843" transparent opacity={0.8} />
      </mesh>

      {/* Receiving / raw-material staging at the west side. */}
      <mesh position={[-22, 0.018, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[7, 36]} />
        <meshBasicMaterial color="#20292e" transparent opacity={0.52} />
      </mesh>

      {/* Ground outside the factory slab. */}
      <mesh position={[0, -0.39, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[160, 160]} />
        <meshStandardMaterial
          color="#0a0e12"
          roughness={0.98}
          metalness={0.02}
        />
      </mesh>
    </group>
  );
}
function Pillars() {
  const pillars = useMemo(() => {
    const result = [];
    const xs = _pillarXPositions();
    PILLAR_ROWS_Z.forEach((z, rowIdx) => {
      xs.forEach((x, i) => {
        result.push({ x, z, id: `pillar-${rowIdx}-${i}` });
      });
    });
    return result;
  }, []);

  return (
    <group>
      {pillars.map((p) => (
        <group key={p.id} position={[p.x, 0, p.z]}>
          <mesh
            position={[0, PILLAR_HEIGHT / 2, 0]}
            castShadow
            receiveShadow
          >
            <boxGeometry args={[0.55, PILLAR_HEIGHT, 0.55]} />
            <meshStandardMaterial
              color="#2d353c"
              roughness={0.68}
              metalness={0.52}
            />
          </mesh>
          <mesh position={[0, 0.05, 0]} castShadow receiveShadow>
            <boxGeometry args={[0.9, 0.1, 0.9]} />
            <meshStandardMaterial
              color="#1a2127"
              roughness={0.85}
              metalness={0.3}
            />
          </mesh>
        </group>
      ))}
    </group>
  );
}

function StructuralBeams() {
  const beamY = PILLAR_HEIGHT + BEAM_HEIGHT / 2;
  const xs = _pillarXPositions();

  const frameWidth = Math.abs(PILLAR_ROWS_Z[1] - PILLAR_ROWS_Z[0]);
  const frameMidZ = (PILLAR_ROWS_Z[0] + PILLAR_ROWS_Z[1]) / 2;

  return (
    <group>
      {/* Two long beams east-west along each pillar row */}
      {PILLAR_ROWS_Z.map((z, i) => (
        <mesh key={`long-beam-${i}`} position={[HALL_CENTER_X, beamY, z]} castShadow>
          <boxGeometry args={[HALL_WIDTH, BEAM_HEIGHT, 0.7]} />
          <meshStandardMaterial
            color="#242c33"
            roughness={0.72}
            metalness={0.5}
          />
        </mesh>
      ))}

      {/* Transverse beams at each structural pillar x-position */}
      {xs.map((x, i) => (
        <mesh key={`transverse-${i}`} position={[x, beamY, frameMidZ]} castShadow>
          <boxGeometry args={[0.5, BEAM_HEIGHT, frameWidth]} />
          <meshStandardMaterial
            color="#242c33"
            roughness={0.72}
            metalness={0.5}
          />
        </mesh>
      ))}

      {/* Dedicated light support beams — one at each LIGHT_COLUMN_X, at
          a slightly lower y than the structural beams so the light bars
          can hang visibly from them. These are what the hanger rods in
          OverheadLights attach to. */}
      {LIGHT_COLUMN_X.map((x, i) => (
        <mesh
          key={`light-beam-${i}`}
          position={[x, PILLAR_HEIGHT - 0.25, frameMidZ]}
          castShadow
        >
          <boxGeometry args={[0.35, 0.3, frameWidth]} />
          <meshStandardMaterial
            color="#2c353c"
            roughness={0.68}
            metalness={0.55}
          />
        </mesh>
      ))}
    </group>
  );
}

function OverheadLights() {
  // Three columns of light bars (west, middle, east) — matching
  // LIGHT_COLUMN_X. Each column has three bars, one per CNC line
  // (z = -12, 0, +12). That's 9 bars total.
  //
  // Each bar has:
  //   - a hanger rod that runs up from the bar to the light support
  //     beam at PILLAR_HEIGHT - 0.1 (so the rod visibly attaches)
  //   - a small mounting bracket at the top of the rod
  //   - a downward point light
  const lights = useMemo(() => {
    const result = [];
    const zs = [-12, 0, 12];
    LIGHT_COLUMN_X.forEach((x, xi) => {
      zs.forEach((z, zi) => {
        result.push({ id: `light-${xi}-${zi}`, x, z });
      });
    });
    return result;
  }, []);

  // The support beam bottom sits at PILLAR_HEIGHT - 0.25 - 0.15
  // (beam center at PILLAR_HEIGHT - 0.25, height 0.3).
  const SUPPORT_BEAM_BOTTOM = PILLAR_HEIGHT - 0.25 - 0.15;
  const BAR_TOP = SUPPORT_BEAM_BOTTOM - 0.5;
  const HANGER_HEIGHT = SUPPORT_BEAM_BOTTOM - BAR_TOP;

  return (
    <group>
      {lights.map((light) => (
        <group key={light.id} position={[light.x, 0, light.z]}>
          {/* Hanger rod — runs from just below the support beam down to
              the light bar top */}
          <mesh position={[0, BAR_TOP + HANGER_HEIGHT / 2, 0]}>
            <cylinderGeometry args={[0.04, 0.04, HANGER_HEIGHT, 8]} />
            <meshStandardMaterial
              color="#3a444c"
              roughness={0.6}
              metalness={0.65}
            />
          </mesh>

          {/* Mounting bracket at the top of the rod — visible square
              plate that reads as the attachment point */}
          <mesh position={[0, SUPPORT_BEAM_BOTTOM - 0.02, 0]}>
            <boxGeometry args={[0.28, 0.04, 0.28]} />
            <meshStandardMaterial
              color="#2c353c"
              roughness={0.55}
              metalness={0.7}
            />
          </mesh>

          {/* Light bar body — a proper industrial fixture with a
              metal housing and a luminous face */}
          <group position={[0, BAR_TOP - 0.07, 0]}>
            {/* Housing */}
            <mesh castShadow>
              <boxGeometry args={[5.5, 0.16, 0.6]} />
              <meshStandardMaterial
                color="#2d363d"
                roughness={0.6}
                metalness={0.55}
              />
            </mesh>
            {/* Luminous downward face */}
            <mesh position={[0, -0.085, 0]}>
              <boxGeometry args={[5.3, 0.02, 0.48]} />
              <meshStandardMaterial
                color="#e8eef2"
                emissive="#c8d0d6"
                emissiveIntensity={1.8}
                roughness={0.35}
              />
            </mesh>
          </group>

          {/* Downward fill light */}
          <pointLight
            intensity={90}
            distance={18}
            decay={2}
            color="#dde4e8"
            position={[0, BAR_TOP - 0.55, 0]}
            castShadow={false}
          />
        </group>
      ))}
    </group>
  );
}

function LogisticsZone() {
  // Keep the finished-goods area on both sides of the east-west shipping
  // aisle. The center aisle remains open so material can move directly from
  // final inspection to finished goods and then to the loading dock.
  const rackRows = [9.1, 14.9];
  const palletRows = [9.0, 15.0];

  return (
    <group>
      {/* Finished-goods pallet racks. */}
      {rackRows.map((z, row) => (
        <group key={`rack-row-${row}`} position={[19.2, 0, z]}>
          <mesh position={[0, 1.25, 0]} castShadow>
            <boxGeometry args={[7.0, 0.12, 0.12]} />
            <meshStandardMaterial
              color="#4a555c"
              roughness={0.72}
              metalness={0.55}
            />
          </mesh>
          <mesh position={[0, 2.35, 0]} castShadow>
            <boxGeometry args={[7.0, 0.12, 0.12]} />
            <meshStandardMaterial
              color="#4a555c"
              roughness={0.72}
              metalness={0.55}
            />
          </mesh>
          {[-3.3, 3.3].map((x, i) => (
            <mesh key={`upright-${i}`} position={[x, 1.8, 0]} castShadow>
              <boxGeometry args={[0.12, 3.6, 0.12]} />
              <meshStandardMaterial
                color="#303a41"
                roughness={0.7}
                metalness={0.6}
              />
            </mesh>
          ))}
          <mesh position={[0, 0.55, 0]} receiveShadow>
            <boxGeometry args={[6.8, 0.1, 0.55]} />
            <meshStandardMaterial
              color="#20282e"
              roughness={0.85}
              metalness={0.2}
            />
          </mesh>
        </group>
      ))}

      {/* Finished-goods pallets are deliberately outside the travel aisle. */}
      {palletRows.flatMap((z, row) =>
        [17.0, 19.2, 21.4].map((x, i) => (
          <group key={`fg-pallet-${row}-${i}`} position={[x, 0, z]}>
            <mesh position={[0, 0.12, 0]} castShadow>
              <boxGeometry args={[1.35, 0.18, 1.0]} />
              <meshStandardMaterial
                color="#4a555c"
                roughness={0.8}
                metalness={0.18}
              />
            </mesh>
            <mesh position={[0, 0.42, 0]} castShadow>
              <boxGeometry args={[1.05, 0.48, 0.72]} />
              <meshStandardMaterial
                color="#6c777d"
                roughness={0.78}
                metalness={0.15}
              />
            </mesh>
          </group>
        ))
      )}

      {/* Compact forklifts/tugs remain in the loading-side maneuvering area. */}
      {[9.0, 15.0].map((z, i) => (
        <group key={`forklift-${i}`} position={[23.0, 0, z]}>
          <mesh position={[0, 0.42, 0]} castShadow>
            <boxGeometry args={[1.5, 0.72, 1.05]} />
            <meshStandardMaterial
              color="#39444b"
              roughness={0.68}
              metalness={0.48}
            />
          </mesh>
          <mesh position={[0.58, 0.98, 0]} castShadow>
            <boxGeometry args={[0.16, 1.15, 0.72]} />
            <meshStandardMaterial
              color="#252d33"
              roughness={0.62}
              metalness={0.58}
            />
          </mesh>
          <mesh position={[0.85, 0.22, 0]} castShadow>
            <boxGeometry args={[0.8, 0.08, 0.72]} />
            <meshStandardMaterial
              color="#59656c"
              roughness={0.55}
              metalness={0.62}
            />
          </mesh>
          {[-0.48, 0.48].map((wz, wi) => (
            <mesh
              key={`wheel-${wi}`}
              position={[-0.35, 0.18, wz]}
              rotation={[Math.PI / 2, 0, 0]}
            >
              <cylinderGeometry args={[0.2, 0.2, 0.14, 16]} />
              <meshStandardMaterial
                color="#11171b"
                roughness={0.9}
                metalness={0.05}
              />
            </mesh>
          ))}
        </group>
      ))}

      {/* Loading dock / truck interface. */}
      <mesh position={[27.4, 0.28, 12]} castShadow receiveShadow>
        <boxGeometry args={[0.35, 0.55, 8.5]} />
        <meshStandardMaterial
          color="#343e44"
          roughness={0.8}
          metalness={0.42}
        />
      </mesh>
      <mesh position={[29.0, 0.12, 12]} receiveShadow>
        <boxGeometry args={[2.4, 0.22, 8.5]} />
        <meshStandardMaterial
          color="#1c252a"
          roughness={0.9}
          metalness={0.08}
        />
      </mesh>

      {/* Two dock door frames. */}
      {[9.2, 14.8].map((z, i) => (
        <group key={`dock-door-${i}`} position={[27.1, 2.2, z]}>
          <mesh position={[0, 0, -1.65]} castShadow>
            <boxGeometry args={[0.18, 4.2, 0.18]} />
            <meshStandardMaterial color="#515c63" roughness={0.7} metalness={0.5} />
          </mesh>
          <mesh position={[0, 0, 1.65]} castShadow>
            <boxGeometry args={[0.18, 4.2, 0.18]} />
            <meshStandardMaterial color="#515c63" roughness={0.7} metalness={0.5} />
          </mesh>
          <mesh position={[0, 2.0, 0]} castShadow>
            <boxGeometry args={[0.18, 0.18, 3.5]} />
            <meshStandardMaterial color="#515c63" roughness={0.7} metalness={0.5} />
          </mesh>
        </group>
      ))}
    </group>
  );
}
export default function FactoryEnvironment() {
  return (
    <group>
      <Floor />
      <Pillars />
      <StructuralBeams />
      <OverheadLights />
      <LogisticsZone />

      <directionalLight
        position={[30, 45, 20]}
        intensity={8}
        color="#f0ede6"
        castShadow
        shadow-mapSize-width={2048}
        shadow-mapSize-height={2048}
        shadow-camera-near={1}
        shadow-camera-far={160}
        shadow-camera-left={-50}
        shadow-camera-right={50}
        shadow-camera-top={50}
        shadow-camera-bottom={-50}
        shadow-bias={-0.0005}
      />
      <directionalLight
        position={[-30, 25, -20]}
        intensity={3}
        color="#8fa5b8"
      />
      <directionalLight
        position={[-12, 18, -44]}
        intensity={2}
        color="#c8d0d4"
      />
      <hemisphereLight
        skyColor="#5b6772"
        groundColor="#0e1418"
        intensity={1.0}
      />
      <ambientLight intensity={0.25} />
    </group>
  );
}