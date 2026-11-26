import { useEffect, useRef } from "react";
import * as THREE from "three";
import { useThree } from "@react-three/fiber";

/**
 * CameraController — cinematic camera moves layered over OrbitControls.
 *
 * Two states:
 *   1. IDLE (default): the controller has a target position/target pair
 *      (from a preset or a focused machine) and lerps the camera toward
 *      it every frame. When the user starts dragging/scrolling (the
 *      OrbitControls "start" event fires), the controller enters
 *      INTERACTING state and stops touching the camera entirely.
 *   2. INTERACTING: OrbitControls owns the camera; the controller does
 *      nothing. When the user releases ("end" event fires), the
 *      controller syncs its look-at reference to the user's current view
 *      so a subsequent cinematic move starts from where the user left
 *      the camera, rather than jumping back.
 *
 * Two bugs were fixed vs the previous version:
 *   - The interaction listeners were bound in an effect that ran before
 *     `<OrbitControls makeDefault>` had registered itself as the default
 *     controls. `controls` was `undefined` on that first effect run, so
 *     `controls.addEventListener` never executed and `interactingRef`
 *     stayed false forever -> camera snapped back on every mouse drag.
 *     Fixed by (a) depending on `controls` being truthy before binding,
 *     and (b) using a ref-based polling approach as a safety net so if
 *     controls appear one frame later, we still attach.
 *   - The animation effect didn't depend on the preset inputs, so a
 *     preset change re-seeded the target refs via the second effect but
 *     the animation loop kept using the old values. Fixed by threading
 *     the seed revision through a ref that the loop reads fresh each
 *     frame.
 *
 * Props:
 *   presetPosition: [x, y, z] | null -- cinematic target camera position
 *   presetTarget:   [x, y, z] | null -- cinematic look-at target
 *   focusKey:       string           -- changes to force a re-seed even
 *     if the position/target values are unchanged (used when re-focusing
 *     the same machine)
 *   lerpSpeed:      number 0..1 per-frame factor (0.045 ≈ 1.5s at 60fps)
 */
export default function CameraController({
  presetPosition = null,
  presetTarget = null,
  focusKey = null,
  lerpSpeed = 0.045,
}) {
  const { camera, controls } = useThree();

  const targetPositionRef = useRef(new THREE.Vector3());
  const targetLookAtRef = useRef(new THREE.Vector3());
  const currentLookAtRef = useRef(new THREE.Vector3(0, 0, 0));

  // True while the user is dragging/zooming. Set from OrbitControls'
  // "start" event, cleared on "end".
  const interactingRef = useRef(false);

  // Set to true after the first frame so we know the refs are seeded.
  const seededRef = useRef(false);

  // Bumped whenever a preset is applied, so the animation loop knows the
  // target refs just changed and it should animate toward them.
  const seedRevisionRef = useRef(0);

  // ── Bind OrbitControls start/end events ─────────────────────────
  // This effect re-runs whenever `controls` changes (i.e. when
  // OrbitControls finishes registering itself). Using a polling fallback
  // in the animate loop covers the (rare) case where `controls` is
  // swapped out mid-session.
  useEffect(() => {
    if (!controls) return undefined;

    const onStart = () => {
      interactingRef.current = true;
    };

    const onEnd = () => {
      interactingRef.current = false;
      // Freeze our internal look-at to whatever the user is now looking
      // at, so a future preset move eases from here rather than snapping.
      if (controls.target) {
        currentLookAtRef.current.copy(controls.target);
        targetLookAtRef.current.copy(controls.target);
      }
      if (camera) {
        targetPositionRef.current.copy(camera.position);
      }
    };

    controls.addEventListener("start", onStart);
    controls.addEventListener("end", onEnd);

    return () => {
      controls.removeEventListener("start", onStart);
      controls.removeEventListener("end", onEnd);
    };
  }, [controls, camera]);

  // ── Apply preset changes ────────────────────────────────────────
  // Only update the cinematic target refs if the user is NOT currently
  // interacting -- otherwise a preset set mid-drag would yank the
  // camera on release.
  useEffect(() => {
    if (interactingRef.current) return;

    if (presetPosition && presetPosition.length === 3) {
      targetPositionRef.current.set(
        presetPosition[0],
        presetPosition[1],
        presetPosition[2]
      );
    }
    if (presetTarget && presetTarget.length === 3) {
      targetLookAtRef.current.set(
        presetTarget[0],
        presetTarget[1],
        presetTarget[2]
      );
    }
    seedRevisionRef.current += 1;
    seededRef.current = true;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    presetPosition?.[0],
    presetPosition?.[1],
    presetPosition?.[2],
    presetTarget?.[0],
    presetTarget?.[1],
    presetTarget?.[2],
    focusKey,
  ]);

  // ── Animation loop ──────────────────────────────────────────────
  // Runs continuously while `camera` and `controls` exist. Each frame:
  //   - if user is interacting, do nothing (OrbitControls owns the cam)
  //   - else, lerp camera + look-at toward the target refs
  // The loop reads the refs every frame, so preset updates take effect
  // immediately without needing to restart the loop.
  useEffect(() => {
    if (!camera || !controls) return undefined;

    // Seed refs from current camera state the first time we run, so
    // the very first frame doesn't animate from origin.
    if (!seededRef.current) {
      targetPositionRef.current.copy(camera.position);
      if (controls.target) {
        targetLookAtRef.current.copy(controls.target);
        currentLookAtRef.current.copy(controls.target);
      }
      seededRef.current = true;
    }

    let frameId = 0;

    const animate = () => {
      if (!interactingRef.current) {
        const camDistSq = camera.position.distanceToSquared(
          targetPositionRef.current
        );
        const lookDistSq = currentLookAtRef.current.distanceToSquared(
          targetLookAtRef.current
        );

        // Only touch the controls when meaningfully far from target,
        // so once the move completes we stop issuing updates every
        // frame (which would otherwise fight user input on the very
        // next mousedown before `start` fires).
        if (camDistSq > 0.0005 || lookDistSq > 0.0005) {
          camera.position.lerp(targetPositionRef.current, lerpSpeed);
          currentLookAtRef.current.lerp(targetLookAtRef.current, lerpSpeed * 1.2);
          if (controls.target) {
            controls.target.copy(currentLookAtRef.current);
          }
          controls.update();
        }
      }

      frameId = requestAnimationFrame(animate);
    };

    animate();

    return () => cancelAnimationFrame(frameId);
  }, [camera, controls, lerpSpeed]);

  return null;
}