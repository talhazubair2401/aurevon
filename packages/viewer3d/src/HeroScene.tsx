"use client";

/**
 * The hero's 3D garment: one model hanging in a dark indigo space under a warm amber key light. Motion is
 * restrained: a baked cloth loop when the garment was delivered with one, otherwise a ±1° sway. A mouse or
 * trackpad can turn it up to ±30°; it springs back on release. No orbit controls, zoom or auto-rotation.
 */
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import type { HeroSceneProps } from "./HeroViewer";
import styles from "./hero.module.css";
import { download } from "./glb";
import { disposeObject, fitToStage, type LoadedModel, loadModel, Variants } from "./loader";

const FLOOR = -1.55;
const AMBER = 0xd99a32;
const SOFT_AMBER = 0xe8b968;
const DEEP_INDIGO = 0x191d35;
const TURN_LIMIT = 0.52; // ±30°

function Environment() {
  const { gl, scene } = useThree();
  useEffect(() => {
    const pmrem = new THREE.PMREMGenerator(gl);
    const env = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environment = env;
    return () => {
      scene.environment = null;
      env.dispose();
      pmrem.dispose();
    };
  }, [gl, scene]);
  return null;
}

function Garment({
  src,
  decoderPath,
  variant,
  turn,
  onReady,
  onFail,
}: Omit<HeroSceneProps, "active" | "draggable"> & { turn: { current: number } }) {
  const [group, setGroup] = useState<THREE.Group | null>(null);
  const mixer = useRef<THREE.AnimationMixer | null>(null);
  const rotation = useRef(0);

  useEffect(() => {
    const abort = new AbortController();
    let loaded: LoadedModel | null = null;
    let variants: Variants | null = null;
    let wrapper: THREE.Group | null = null;
    (async () => {
      const buf = await download(src, () => undefined, abort.signal);
      loaded = await loadModel(buf, decoderPath);
      variants = new Variants(loaded);
      await variants.select(variant);
      wrapper = fitToStage(loaded.scene, FLOOR);
      const clip = loaded.animations[0];
      if (clip) {
        mixer.current = new THREE.AnimationMixer(loaded.scene);
        mixer.current.clipAction(clip).play();
      }
      if (abort.signal.aborted) return;
      setGroup(wrapper);
      onReady();
    })().catch((error: unknown) => {
      if (!abort.signal.aborted) onFail(error);
    });
    return () => {
      abort.abort();
      mixer.current?.stopAllAction();
      mixer.current = null;
      if (wrapper) disposeObject(wrapper, variants?.materials() ?? []);
    };
    // The hero shows one garment; a new src remounts the scene.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [src, decoderPath, variant]);

  useFrame((state, delta) => {
    if (!group) return;
    const t = state.clock.elapsedTime;
    if (mixer.current) mixer.current.update(Math.min(delta, 0.05));
    else {
      group.rotation.z = Math.sin((t * Math.PI * 2) / 5) * 0.017; // about 1°, a 5 s loop
      group.position.x = Math.sin((t * Math.PI * 2) / 5) * 0.01;
    }
    // Ease toward the dragged angle; with no drag the target is 0, so it springs back.
    rotation.current += (turn.current - rotation.current) * Math.min(1, delta * 6);
    group.rotation.y = rotation.current;
  });

  return group ? <primitive object={group} /> : null;
}

function Lights() {
  return (
    <>
      <color attach="background" args={[0x111322]} />
      <fog attach="fog" args={[0x111322, 8, 16]} />
      <hemisphereLight args={[0xfff1e0, DEEP_INDIGO, 0.35]} />
      {/* Warm key from upper left, as in a garment studio; amber rim from behind for the silhouette. */}
      <spotLight
        color={0xffe2b8}
        intensity={60}
        angle={0.5}
        penumbra={0.8}
        distance={20}
        position={[-3.2, 5.5, 4.5]}
      />
      <pointLight color={AMBER} intensity={10} distance={9} position={[2.6, 1.8, -2.6]} />
      <pointLight color={SOFT_AMBER} intensity={4} distance={8} position={[-2.4, -0.6, -2]} />
    </>
  );
}

export default function HeroScene({
  src,
  decoderPath,
  variant,
  active,
  draggable,
  onReady,
  onFail,
}: HeroSceneProps) {
  const turn = useRef(0);
  const drag = useRef<{ x: number; base: number } | null>(null);

  const handlers = draggable
    ? {
        onPointerDown: (e: React.PointerEvent<HTMLDivElement>) => {
          drag.current = { x: e.clientX, base: turn.current };
          e.currentTarget.setPointerCapture(e.pointerId);
        },
        onPointerMove: (e: React.PointerEvent<HTMLDivElement>) => {
          if (!drag.current) return;
          const next = drag.current.base + (e.clientX - drag.current.x) * 0.005;
          turn.current = Math.max(-TURN_LIMIT, Math.min(TURN_LIMIT, next));
        },
        onPointerUp: () => {
          drag.current = null;
          turn.current = 0;
        },
        onPointerCancel: () => {
          drag.current = null;
          turn.current = 0;
        },
      }
    : {};

  return (
    <div className={styles.scene} {...handlers}>
      <Canvas
        frameloop={active ? "always" : "never"}
        dpr={[1, 1.5]}
        camera={{ position: [0, 0.15, 7.6], fov: 30 }}
        gl={{ antialias: true, alpha: false, powerPreference: "high-performance" }}
        onCreated={({ gl }) => {
          gl.toneMapping = THREE.ACESFilmicToneMapping;
          gl.toneMappingExposure = 1.05;
          gl.outputColorSpace = THREE.SRGBColorSpace;
        }}
      >
        <Environment />
        <Lights />
        <Garment
          src={src}
          decoderPath={decoderPath}
          variant={variant}
          turn={turn}
          onReady={onReady}
          onFail={onFail}
        />
      </Canvas>
    </div>
  );
}
