"use client";

/**
 * The 3D scene (React Three Fiber over three.js), loaded on the client only, after the poster is on screen
 * (MTS §4). Stage as approved in v1/v2: gallery environment, plinth, lights, gold accents (gold mainly in 3D,
 * A-03). Controls: rotate, two-finger tilt and pinch, `touch-action: pan-y`, keyboard, time-based camera moves;
 * the mouse wheel scrolls the page and Ctrl/⌘ + wheel zooms (decision 0007, D-05).
 */
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useSyncExternalStore } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { download, ModelError } from "./glb";
import { disposeObject, fitToStage, loadModel, Variants } from "./loader";
import { shouldRender, type ViewerStore } from "./state";

const FLOOR = -1.55;
const HOME = new THREE.Vector3(0, 0.55, 7.9);
const GOLD = 0xd99a32; // Amber (decision 0008)

export interface CameraApi {
  zoom: (factor: number) => void;
  reset: () => void;
  distance: () => number;
}

export interface SceneProps {
  store: ViewerStore;
  url: string;
  decoderPath: string;
  /** Material variant for the selected colour; "" shows the model as delivered. */
  variant: string;
  viewerLabel: string;
  reducedMotion: boolean;
  cameraApi: { current: CameraApi | null };
  onWheelWithoutModifier: () => void;
  onKeyboardFocus: (focused: boolean) => void;
  onLoaded: (info: { decoder: string | null; ms: number }) => void;
}

function useViewer(store: ViewerStore) {
  return useSyncExternalStore(store.subscribe, store.get, store.get);
}

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

function Stage({ reducedMotion }: { reducedMotion: boolean }) {
  const shadowTexture = useMemo(() => {
    const c = document.createElement("canvas");
    c.width = c.height = 256;
    const g = c.getContext("2d")!;
    const gradient = g.createRadialGradient(128, 128, 0, 128, 128, 128);
    gradient.addColorStop(0, "rgba(0,0,0,0.55)");
    gradient.addColorStop(1, "rgba(0,0,0,0)");
    g.fillStyle = gradient;
    g.fillRect(0, 0, 256, 256);
    return new THREE.CanvasTexture(c);
  }, []);
  const motes = useMemo(() => {
    const n = 140;
    const a = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      a[i * 3] = (Math.random() - 0.5) * 7;
      a[i * 3 + 1] = Math.random() * 4.2 - 1.6;
      a[i * 3 + 2] = (Math.random() - 0.5) * 5 - 1;
    }
    return a;
  }, []);
  useEffect(() => () => shadowTexture.dispose(), [shadowTexture]);
  const shadow = useRef<THREE.Mesh>(null);
  const dust = useRef<THREE.Points>(null);
  useFrame(({ clock }) => {
    if (reducedMotion || !shadow.current || !dust.current) return;
    const t = clock.elapsedTime;
    shadow.current.scale.setScalar(1 - Math.sin(t * 0.9) * 0.03);
    dust.current.rotation.y = t * 0.02;
    dust.current.position.y = Math.sin(t * 0.3) * 0.05;
  });
  return (
    <>
      <fog attach="fog" args={[0x141729, 9, 18]} />
      <hemisphereLight args={[0xfff4e6, 0x191d35, 0.55]} />
      <directionalLight color={0xfff1df} intensity={2.2} position={[2.5, 4, 4]} />
      <directionalLight color={0xe9dccb} intensity={0.6} position={[-4, 1.5, 2]} />
      <pointLight color={GOLD} intensity={14} distance={10} position={[-2.4, 1.6, -2.2]} />
      <pointLight color={GOLD} intensity={10} distance={10} position={[2.6, 0.4, -2.4]} />
      <mesh position={[0, FLOOR - 0.06, 0]}>
        <cylinderGeometry args={[1.35, 1.42, 0.12, 96]} />
        <meshStandardMaterial
          color={0x111322}
          roughness={0.55}
          metalness={0}
          envMapIntensity={0.25}
        />
      </mesh>
      <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, FLOOR + 0.002, 0]}>
        <torusGeometry args={[1.36, 0.012, 12, 160]} />
        <meshStandardMaterial color={GOLD} metalness={1} roughness={0.22} envMapIntensity={1.4} />
      </mesh>
      <mesh ref={shadow} rotation={[-Math.PI / 2, 0, 0]} position={[0, FLOOR + 0.004, 0]}>
        <planeGeometry args={[2.2, 2.2]} />
        <meshBasicMaterial map={shadowTexture} transparent depthWrite={false} />
      </mesh>
      <points ref={dust}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[motes, 3]} />
        </bufferGeometry>
        <pointsMaterial color={GOLD} size={0.018} transparent opacity={0.55} depthWrite={false} />
      </points>
    </>
  );
}

interface Animation {
  start: number;
  a0: number;
  a1: number;
  r0: number;
  r1: number;
  y0: number;
  y1: number;
}

function Controls(
  props: Pick<
    SceneProps,
    | "store"
    | "viewerLabel"
    | "reducedMotion"
    | "cameraApi"
    | "onWheelWithoutModifier"
    | "onKeyboardFocus"
  >,
) {
  const { store, viewerLabel, reducedMotion, cameraApi, onWheelWithoutModifier, onKeyboardFocus } =
    props;
  const { camera, gl, size } = useThree();
  const controls = useRef<OrbitControls | null>(null);
  const anim = useRef<Animation | null>(null);

  useEffect(() => {
    (camera as THREE.PerspectiveCamera).fov = size.width / size.height < 0.85 ? 36 : 32;
    camera.updateProjectionMatrix();
  }, [size, camera]);

  useEffect(() => {
    const c = new OrbitControls(camera, gl.domElement);
    c.target.set(0, 0.05, 0);
    c.enableDamping = true;
    c.dampingFactor = 0.06;
    c.enablePan = false;
    c.minDistance = 3.2;
    c.maxDistance = 10.5;
    c.minPolarAngle = Math.PI * 0.22;
    c.maxPolarAngle = Math.PI * 0.58;
    c.autoRotateSpeed = 0.9;
    // One finger rotates; two fingers pinch to zoom and drag to tilt.
    c.touches = { ONE: THREE.TOUCH.ROTATE, TWO: THREE.TOUCH.DOLLY_ROTATE };
    c.addEventListener("start", () => {
      anim.current = null;
    });
    controls.current = c;
    const el = gl.domElement;
    // OrbitControls blocks every touch gesture; vertical swipes go back to the page so it can scroll.
    el.style.touchAction = "pan-y";
    el.tabIndex = 0;
    el.setAttribute("role", "application");
    el.setAttribute("aria-roledescription", "3D viewer");
    el.setAttribute("aria-label", viewerLabel);

    const spherical = new THREE.Spherical();
    const offset = new THREE.Vector3();
    const orbit = (dTheta: number, dPhi: number, scale: number) => {
      anim.current = null;
      offset.copy(camera.position).sub(c.target);
      spherical.setFromVector3(offset);
      spherical.theta += dTheta;
      spherical.phi = THREE.MathUtils.clamp(spherical.phi + dPhi, c.minPolarAngle, c.maxPolarAngle);
      spherical.radius = THREE.MathUtils.clamp(
        spherical.radius * scale,
        c.minDistance,
        c.maxDistance,
      );
      camera.position.setFromSpherical(spherical).add(c.target);
    };

    // D-05: the wheel scrolls the page; Ctrl/⌘ + wheel zooms (trackpad pinch arrives as Ctrl + wheel).
    // Runs in the capture phase, before OrbitControls' own wheel listener, which never sees the event.
    const onWheel = (e: WheelEvent) => {
      e.stopImmediatePropagation();
      if (!e.ctrlKey && !e.metaKey) {
        onWheelWithoutModifier();
        return; // not prevented: the page scrolls
      }
      e.preventDefault(); // stops browser page zoom
      const delta = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY;
      orbit(0, 0, Math.exp(THREE.MathUtils.clamp(delta, -100, 100) * 0.004));
    };
    const onKey = (e: KeyboardEvent) => {
      const map: Record<string, [number, number, number]> = {
        ArrowLeft: [-1, 0, 1],
        ArrowRight: [1, 0, 1],
        ArrowUp: [0, -1, 1],
        ArrowDown: [0, 1, 1],
        "+": [0, 0, 0.85],
        "=": [0, 0, 0.85],
        "-": [0, 0, 1 / 0.85],
        _: [0, 0, 1 / 0.85],
      };
      if (e.key === "Home") {
        e.preventDefault();
        cameraApi.current?.reset();
        return;
      }
      const m = map[e.key];
      if (!m) return;
      e.preventDefault();
      if (store.get().autoRotate) store.set({ autoRotate: false });
      orbit((m[0] * Math.PI) / 12, (m[1] * Math.PI) / 18, m[2]);
    };
    const onFocus = () => onKeyboardFocus(el.matches(":focus-visible"));
    const onBlur = () => onKeyboardFocus(false);
    el.addEventListener("wheel", onWheel, { capture: true, passive: false });
    el.addEventListener("keydown", onKey);
    el.addEventListener("focus", onFocus);
    el.addEventListener("blur", onBlur);

    cameraApi.current = {
      zoom: (factor) => orbit(0, 0, factor),
      distance: () => camera.position.distanceTo(c.target),
      reset: () => {
        store.set({ autoRotate: !reducedMotion });
        const flat = Math.hypot(HOME.x, HOME.z);
        if (reducedMotion) {
          camera.position.set(0, HOME.y, flat);
          anim.current = null;
          return;
        }
        anim.current = {
          start: performance.now(),
          a0: Math.atan2(camera.position.x, camera.position.z),
          a1: 0,
          r0: Math.hypot(camera.position.x, camera.position.z),
          r1: flat,
          y0: camera.position.y,
          y1: HOME.y,
        };
      },
    };
    return () => {
      el.removeEventListener("wheel", onWheel, { capture: true });
      el.removeEventListener("keydown", onKey);
      el.removeEventListener("focus", onFocus);
      el.removeEventListener("blur", onBlur);
      c.dispose();
      controls.current = null;
      cameraApi.current = null;
    };
  }, [
    camera,
    gl,
    store,
    viewerLabel,
    reducedMotion,
    cameraApi,
    onWheelWithoutModifier,
    onKeyboardFocus,
  ]);

  useFrame((_, dt) => {
    const c = controls.current;
    if (!c) return;
    c.autoRotate = store.get().autoRotate;
    const a = anim.current;
    if (a) {
      // Time-based, so a slow device takes the same 1.1 s as a fast one.
      const p = Math.min((performance.now() - a.start) / 1100, 1);
      const e = p < 0.5 ? 4 * p ** 3 : 1 - Math.pow(-2 * p + 2, 3) / 2;
      let da = a.a1 - a.a0;
      if (da > Math.PI) da -= 2 * Math.PI;
      if (da < -Math.PI) da += 2 * Math.PI;
      const angle = a.a0 + da * e;
      const r = a.r0 + (a.r1 - a.r0) * e;
      camera.position.set(Math.sin(angle) * r, a.y0 + (a.y1 - a.y0) * e, Math.cos(angle) * r);
      if (p >= 1) anim.current = null;
    }
    c.update(dt);
  });
  return null;
}

/** Loads the model, keeps the selected variant on it, and frees everything when it goes (D1, dispose). */
function Garment({
  store,
  url,
  decoderPath,
  variant,
  reducedMotion,
  onLoaded,
}: Pick<SceneProps, "store" | "url" | "decoderPath" | "variant" | "reducedMotion" | "onLoaded">) {
  const s = useViewer(store);
  const float = useRef<THREE.Group>(null);
  const holder = useRef<{ root: THREE.Group; variants: Variants } | null>(null);
  const variantRef = useRef(variant);
  const { gl, camera, scene, invalidate } = useThree();
  const frames = useRef(-1);

  useEffect(() => {
    const abort = new AbortController();
    let cancelled = false;
    const t0 = performance.now();
    (async () => {
      try {
        const buf = await download(
          url,
          (f) => store.set({ progress: 0.3 + 0.5 * f }),
          abort.signal,
        );
        if (cancelled) return;
        const model = await loadModel(buf, decoderPath);
        if (cancelled) {
          disposeObject(model.scene);
          return;
        }
        const root = fitToStage(model.scene, FLOOR);
        const variants = new Variants(model);
        await variants.select(variantRef.current);
        await gl.compileAsync(root, camera, scene).catch(() => undefined);
        if (cancelled) {
          disposeObject(root, variants.materials());
          return;
        }
        holder.current = { root, variants };
        float.current?.add(root);
        frames.current = 0; // first frames, then ready (Warmup below)
        store.set({ progress: 0.95 });
        onLoaded({
          decoder: (model.decoder as string | null) ?? null,
          ms: Math.round(performance.now() - t0),
        });
        invalidate();
      } catch (error) {
        if (cancelled || (error as Error).name === "AbortError") return;
        const code = error instanceof ModelError ? error.code : "corrupt";
        const message = error instanceof Error ? error.message : String(error);
        console.warn("[viewer3d] model failed:", code, message);
        store.fail("model", code, message);
      }
    })();
    return () => {
      cancelled = true;
      abort.abort();
      const held = holder.current;
      holder.current = null;
      if (held) {
        held.root.removeFromParent();
        // After React has swapped it out.
        setTimeout(() => disposeObject(held.root, held.variants.materials()), 0);
      }
    };
  }, [url, decoderPath, store, gl, camera, scene, invalidate, onLoaded]);

  useEffect(() => {
    variantRef.current = variant;
    holder.current?.variants.select(variant).then(() => invalidate());
  }, [variant, invalidate]);

  useFrame(({ clock }) => {
    if (frames.current >= 0) {
      frames.current++;
      if (frames.current === 2 && store.get().phase === "loading")
        store.set({ phase: "ready", progress: 1 });
    }
    if (reducedMotion || !float.current) return;
    const t = clock.elapsedTime;
    float.current.position.y = Math.sin(t * 0.9) * 0.045;
    float.current.rotation.z = Math.sin(t * 0.55) * 0.012;
  });
  void s;
  return <group ref={float} />;
}

export default function Scene(props: SceneProps) {
  const s = useViewer(props.store);
  const { store } = props;
  if (s.phase === "lost") return null; // the dead canvas unmounts; Try again mounts a fresh one
  return (
    <Canvas
      key={s.attempt}
      frameloop={shouldRender(s) || !s.canvasMounted ? "always" : "never"}
      dpr={[1, 2]}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      camera={{ fov: 32, near: 0.1, far: 50, position: [HOME.x, HOME.y, HOME.z] }}
      onCreated={({ gl }) => {
        const attempt = store.get().attempt;
        gl.toneMappingExposure = 1.05;
        gl.setClearColor(0x000000, 0);
        gl.domElement.addEventListener(
          "webglcontextlost",
          (e) => {
            // Unmounting for Try again (or leaving the page) also loses the context: not a failure.
            if (store.get().attempt !== attempt) return;
            e.preventDefault();
            console.warn("[viewer3d] WebGL context lost");
            store.set({ phase: "lost", canvasMounted: false });
          },
          { once: true },
        );
        store.set({ canvasMounted: true });
      }}
    >
      <Environment />
      <Stage reducedMotion={props.reducedMotion} />
      <Garment
        store={store}
        url={props.url}
        decoderPath={props.decoderPath}
        variant={props.variant}
        reducedMotion={props.reducedMotion}
        onLoaded={props.onLoaded}
      />
      <Controls
        store={store}
        viewerLabel={props.viewerLabel}
        reducedMotion={props.reducedMotion}
        cameraApi={props.cameraApi}
        onWheelWithoutModifier={props.onWheelWithoutModifier}
        onKeyboardFocus={props.onKeyboardFocus}
      />
    </Canvas>
  );
}
