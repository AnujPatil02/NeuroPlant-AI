import React, {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Canvas } from "@react-three/fiber";
import {
  OrbitControls,
  PerspectiveCamera,
} from "@react-three/drei";

import FactoryEnvironment from "./FactoryEnvironment";
import ProductionMachines, {
  getFactoryMachinePosition,
} from "./ProductionMachines";

import TwinLabels from "../ui/TwinLabels";
import TwinHUD from "../ui/TwinHUD";
import MachineInspector from "../ui/MachineInspector";
import SceneOverlays from "../ui/SceneOverlays";

import CameraController from "../interaction/CameraController";

import {
  getMachineCounts,
  getSelectedMachine,
} from "../data/twinState";

import "../styles/twin.css";

const CAMERA_PRESETS = {
  overview: {
    position: [47, 34, 48],
    target: [0, 0, 0],
  },
  machining: {
    position: [32, 17, 31],
    target: [4, 0, -7],
  },
  production: {
    position: [-30, 18, 34],
    target: [-4, 0, 3],
  },
  logistics: {
    position: [42, 22, -31],
    target: [10, 0, 0],
  },
};

function SceneContent({
  machines,
  selectedMachineId,
  onSelect,
  focusMachineId,
  cameraPreset,
  showLabels,
  showFlow,
}) {
  // Resolve the cinematic target from either the active preset or a
  // focused machine. Both feed into CameraController as a single
  // position/target pair; the controller itself does not know which
  // source produced them.
  const { presetPosition, presetTarget, focusKey } = useMemo(() => {
    if (focusMachineId) {
      const p = getFactoryMachinePosition(focusMachineId);
      return {
        presetPosition: [p[0] + 9, p[1] + 7, p[2] + 10],
        presetTarget: [p[0], 1, p[2]],
        focusKey: `machine:${focusMachineId}`,
      };
    }

    const preset = CAMERA_PRESETS[cameraPreset] || CAMERA_PRESETS.overview;
    return {
      presetPosition: preset.position,
      presetTarget: preset.target,
      focusKey: `preset:${cameraPreset}`,
    };
  }, [cameraPreset, focusMachineId]);

  return (
    <>
      <PerspectiveCamera
        makeDefault
        position={CAMERA_PRESETS.overview.position}
        fov={45}
        near={0.1}
        far={250}
      />

      <FactoryEnvironment />

      <ProductionMachines
        machines={machines}
        selectedMachineId={selectedMachineId}
        onSelect={onSelect}
      />

      <TwinLabels visible={showLabels} />

      <SceneOverlays showFlow={showFlow} showOrientation />

      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.075}
        rotateSpeed={0.58}
        zoomSpeed={0.9}
        panSpeed={0.75}
        minDistance={7}
        maxDistance={105}
        maxPolarAngle={Math.PI / 2.02}
        minPolarAngle={0.18}
        screenSpacePanning
      />

      <CameraController
        presetPosition={presetPosition}
        presetTarget={presetTarget}
        focusKey={focusKey}
      />
    </>
  );
}

export default function FactoryScene({
  machines = {},
  selectedMachineId,
  onSelectMachine,
  connectionState = "connecting",
  lastUpdated,
  lastError,
  apiBaseUrl,
  onClearSelection,
}) {
  const [cameraPreset, setCameraPreset] = useState("overview");
  const [focusMachineId, setFocusMachineId] = useState(null);
  const [showLabels, setShowLabels] = useState(true);
  const [showFlow, setShowFlow] = useState(true);

  const selectedMachine = useMemo(
    () => getSelectedMachine(machines, selectedMachineId),
    [machines, selectedMachineId]
  );

  const counts = useMemo(() => getMachineCounts(machines), [machines]);

  const selectMachine = useCallback(
    (machineId) => {
      onSelectMachine?.(machineId);
      setFocusMachineId(machineId);
    },
    [onSelectMachine]
  );

  const clearSelection = useCallback(() => {
    setFocusMachineId(null);
    onClearSelection?.();
  }, [onClearSelection]);

  const focusSelected = useCallback(() => {
    if (!selectedMachineId) return;
    // Force a re-focus even if the selected machine did not change by
    // toggling through null for one frame -- CameraController uses the
    // focusKey to know when to re-seed its target vectors.
    setFocusMachineId(null);
    window.requestAnimationFrame(() => {
      setFocusMachineId(selectedMachineId);
    });
  }, [selectedMachineId]);

  useEffect(() => {
    const handleKeyDown = (event) => {
      if (
        event.target instanceof HTMLInputElement ||
        event.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      switch (event.key.toLowerCase()) {
        case "1":
          setCameraPreset("overview");
          setFocusMachineId(null);
          break;
        case "2":
          setCameraPreset("machining");
          setFocusMachineId(null);
          break;
        case "3":
          setCameraPreset("production");
          setFocusMachineId(null);
          break;
        case "4":
          setCameraPreset("logistics");
          setFocusMachineId(null);
          break;
        case "l":
          setShowLabels((v) => !v);
          break;
        case "f":
          setShowFlow((v) => !v);
          break;
        case "escape":
          clearSelection();
          break;
        default:
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [clearSelection]);

  return (
    <div className="twin-shell">
      <div className="twin-canvas">
        <Canvas
          shadows
          dpr={[1, 1.8]}
          gl={{
            antialias: true,
            powerPreference: "high-performance",
          }}
          onPointerMissed={clearSelection}
        >
          <color attach="background" args={["#080b0f"]} />
          <fog attach="fog" args={["#080b0f", 65, 125]} />

          <Suspense fallback={null}>
            <SceneContent
              machines={machines}
              selectedMachineId={selectedMachineId}
              onSelect={selectMachine}
              focusMachineId={focusMachineId}
              cameraPreset={cameraPreset}
              showLabels={showLabels}
              showFlow={showFlow}
            />
          </Suspense>
        </Canvas>
      </div>

      <TwinHUD
        machines={machines}
        selectedMachineId={selectedMachineId}
        connectionState={connectionState}
        lastUpdated={lastUpdated}
        lastError={lastError}
        apiBaseUrl={apiBaseUrl}
      />

      <div className="twin-scene-status">
        <span className="scene-status-primary">
          PRECISION MOBILITY FACTORY
        </span>
        <span className="scene-status-divider">/</span>
        <span>{counts.total} ASSETS</span>
        <span className="scene-status-divider">/</span>
        <span>{counts.running} RUNNING</span>
      </div>

      <div className="twin-view-controls">
        {["overview", "machining", "production", "logistics"].map((preset) => (
          <button
            key={preset}
            type="button"
            className={
              cameraPreset === preset && !focusMachineId
                ? "view-toggle active"
                : "view-toggle"
            }
            onClick={() => {
              setCameraPreset(preset);
              setFocusMachineId(null);
            }}
          >
            {preset.toUpperCase()}
          </button>
        ))}
      </div>

      <div className="twin-layer-controls">
        <button
          type="button"
          className={showLabels ? "layer-toggle active" : "layer-toggle"}
          onClick={() => setShowLabels((v) => !v)}
        >
          LABELS
        </button>
        <button
          type="button"
          className={showFlow ? "layer-toggle active" : "layer-toggle"}
          onClick={() => setShowFlow((v) => !v)}
        >
          MATERIAL FLOW
        </button>
      </div>

      <MachineInspector
        machine={selectedMachine}
        onClose={clearSelection}
        onFocus={focusSelected}
      />
    </div>
  );
}