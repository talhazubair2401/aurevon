"use client";

/**
 * ProductViewer (MTS §4): the product image is the poster and is always on the page first; the 3D view loads after
 * it, takes over when its first frame is ready, and the shopper can go back to the image at any time. Every
 * failure keeps the image and says so, with Try again. The 3D code (three.js, R3F) is fetched only here, on the
 * client, so a page without a model, or a browser without WebGL, never downloads it.
 */
import {
  type ComponentType,
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import type { CameraApi, SceneProps } from "./Scene";
import { is3D, shouldRender, SLOW_AFTER_MS, ViewerStore } from "./state";
import { ENGLISH, type ViewerLabels } from "./strings";
import styles from "./viewer.module.css";

export interface ProductViewerProps {
  /** The approved model's address (shoppers) or a signed preview address (staff). */
  src: string;
  /** Folder that holds the Draco decoder, from `decoderPath()`. */
  decoderPath: string;
  /** Material variant for the selected colour ("" shows the model as delivered). */
  variant?: string;
  /** False when the selected colour has no 3D version: its photos show instead (decision 0007, D-03). */
  colourHas3D?: boolean;
  colourName?: string | undefined;
  labels?: ViewerLabels;
  /** Staff preview: shows the technical reason for a failure. */
  detailedErrors?: boolean;
  className?: string;
  /** The poster: the product's server-rendered image. */
  children: ReactNode;
}

function webGLAvailable(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") ?? canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

const HINT_KEY = "av-3d-hint-seen";
function hintSeen(): boolean {
  try {
    return window.localStorage.getItem(HINT_KEY) === "1";
  } catch {
    return false;
  }
}
function rememberHint(): void {
  try {
    window.localStorage.setItem(HINT_KEY, "1");
  } catch {
    // storage unavailable: the hint may show again, which is harmless
  }
}

function fill(template: string, values: Record<string, string>): string {
  return template.replace(/\{(\w+)\}/g, (_, k: string) => values[k] ?? "");
}

export function ProductViewer({
  src,
  decoderPath,
  variant = "",
  colourHas3D = true,
  colourName,
  labels = ENGLISH,
  detailedErrors = false,
  className,
  children,
}: ProductViewerProps) {
  const [store] = useState(() => new ViewerStore({ colourHas3D }));
  const s = useSyncExternalStore(store.subscribe, store.get, store.get);
  const [Scene, setScene] = useState<ComponentType<SceneProps> | null>(null);
  const [reducedMotion, setReducedMotion] = useState(false);
  const [hint, setHint] = useState<"none" | "first" | "wheel">("none");
  const [keyboard, setKeyboard] = useState(false);
  const [decoder, setDecoder] = useState<string | null>(null);
  const [modKey, setModKey] = useState("Ctrl");
  const [touch, setTouch] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const cameraApi = useRef<CameraApi | null>(null);
  const wheelTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const firstSrc = useRef(src);
  const bar = useRef<HTMLElement>(null);

  // Start: check WebGL, then fetch the 3D code. A failed fetch is a "libraries" failure (Try again reloads).
  useEffect(() => {
    const motion = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    const reduce = Boolean(motion?.matches);
    setReducedMotion(reduce);
    store.set({ autoRotate: !reduce, pageVisible: document.visibilityState !== "hidden" });
    setModKey(/Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent) ? "⌘" : "Ctrl");
    setTouch(window.matchMedia?.("(pointer: coarse)").matches ?? false);
    if (!webGLAvailable()) {
      store.set({ phase: "unavailable" });
      return;
    }
    let cancelled = false;
    import("./Scene")
      .then((m) => {
        if (!cancelled) setScene(() => m.default);
      })
      .catch((error: unknown) => {
        console.warn("[viewer3d] 3D code failed to load:", error);
        if (!cancelled) store.fail("libraries", "libraries", String(error));
      });
    return () => {
      cancelled = true;
    };
  }, [store]);

  // Render only while on screen and in a visible tab (D3).
  useEffect(() => {
    const el = root.current;
    const onVisibility = () => store.set({ pageVisible: document.visibilityState !== "hidden" });
    document.addEventListener("visibilitychange", onVisibility);
    let observer: IntersectionObserver | undefined;
    if (el && typeof IntersectionObserver !== "undefined") {
      observer = new IntersectionObserver(
        ([entry]) => store.set({ visible: Boolean(entry?.isIntersecting) }),
        {
          threshold: 0.01,
        },
      );
      observer.observe(el);
    }
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      observer?.disconnect();
    };
  }, [store]);

  useEffect(() => store.set({ colourHas3D }), [colourHas3D, store]);

  // A colour with its own model: load it, keeping the image up meanwhile.
  useEffect(() => {
    if (src === firstSrc.current) return;
    firstSrc.current = src;
    if (store.get().phase === "ready" || store.get().phase === "failed") {
      store.set({
        phase: "loading",
        progress: 0,
        slow: 0,
        failure: null,
        errorCode: null,
        errorMessage: null,
      });
    }
  }, [src, store]);

  // Slow loads change the message only; they never fail (D4).
  useEffect(() => {
    if (s.phase !== "loading") return;
    store.set({ slow: 0 });
    const timers = SLOW_AFTER_MS.map((ms, i) =>
      setTimeout(() => store.set({ slow: (i + 1) as 1 | 2 }), ms),
    );
    return () => timers.forEach(clearTimeout);
  }, [s.phase, s.attempt, store]);

  // Set through the DOM, not a style attribute: the page's CSP has no 'unsafe-inline' styles (decision 0005).
  useEffect(() => {
    if (bar.current)
      bar.current.style.inlineSize = `${Math.round(Math.max(0.1, s.progress) * 100)}%`;
  });

  const showing3D = is3D(s);
  useEffect(() => {
    if (showing3D && hint === "none" && !hintSeen()) {
      setHint("first");
      rememberHint();
      const t = setTimeout(() => setHint((h) => (h === "first" ? "none" : h)), 5000);
      return () => clearTimeout(t);
    }
  }, [showing3D, hint]);
  useEffect(() => () => clearTimeout(wheelTimer.current), []);

  const onWheelWithoutModifier = useCallback(() => {
    setHint("wheel");
    clearTimeout(wheelTimer.current);
    wheelTimer.current = setTimeout(() => setHint("none"), 1800);
  }, []);
  const onLoaded = useCallback(
    (info: { decoder: string | null; ms: number }) => setDecoder(info.decoder),
    [],
  );

  const tryAgain = () => {
    if (s.failure === "libraries") {
      window.location.reload();
      return;
    }
    store.set({
      phase: "loading",
      attempt: s.attempt + 1,
      progress: 0,
      slow: 0,
      failure: null,
      errorCode: null,
      errorMessage: null,
      canvasMounted: false,
    });
  };

  const status =
    !colourHas3D && (s.phase === "loading" || s.phase === "ready")
      ? labels.noColour
      : s.phase === "loading"
        ? [labels.loading, labels.stillLoading, labels.slow][s.slow]
        : s.phase === "failed"
          ? labels.failed
          : s.phase === "lost"
            ? labels.lost
            : s.phase === "unavailable"
              ? labels.unavailable
              : null;
  const canRetry = s.phase === "failed" || s.phase === "lost";
  const loading = s.phase === "loading" && colourHas3D;
  const hintText =
    hint === "wheel"
      ? fill(labels.wheelHint, { key: modKey })
      : hint === "first"
        ? keyboard
          ? labels.hintKeyboard
          : touch
            ? labels.hintTouch
            : fill(labels.hintPointer, { key: modKey })
        : null;

  return (
    <div
      ref={root}
      className={[styles.viewer, keyboard ? styles.keyboard : "", className ?? ""].join(" ")}
      data-viewer3d=""
      data-phase={s.phase}
      data-showing={showing3D ? "3d" : "image"}
      data-rendering={String(shouldRender(s))}
      data-decoder={decoder ?? ""}
      data-error={s.errorCode ?? ""}
    >
      <div className={styles.poster} aria-hidden={showing3D || undefined}>
        {children}
      </div>

      {Scene && s.phase !== "unavailable" && s.failure !== "libraries" ? (
        <div
          className={showing3D ? styles.canvasShown : styles.canvasHidden}
          aria-hidden={!showing3D || undefined}
        >
          <Scene
            store={store}
            url={src}
            decoderPath={decoderPath}
            variant={variant}
            viewerLabel={labels.viewerLabel}
            reducedMotion={reducedMotion}
            cameraApi={cameraApi}
            onWheelWithoutModifier={onWheelWithoutModifier}
            onKeyboardFocus={setKeyboard}
            onLoaded={onLoaded}
          />
        </div>
      ) : null}

      {showing3D ? (
        <span className={styles.badge} aria-hidden="true">
          {labels.badge}
        </span>
      ) : null}

      <div className={styles.controls}>
        {s.phase === "ready" && colourHas3D ? (
          <button
            type="button"
            className={styles.chip}
            onClick={() => store.set({ userChoseImage: !s.userChoseImage })}
            data-action="toggle"
          >
            {s.userChoseImage ? labels.showThreeD : labels.showImage}
          </button>
        ) : null}
        {showing3D ? (
          <>
            <button
              type="button"
              className={styles.chip}
              aria-pressed={s.autoRotate}
              onClick={() => store.set({ autoRotate: !s.autoRotate })}
              data-action="rotate"
            >
              {labels.rotateOn}
            </button>
            <button
              type="button"
              className={styles.chipIcon}
              aria-label={labels.zoomIn}
              onClick={() => cameraApi.current?.zoom(0.85)}
              data-action="zoom-in"
            >
              +
            </button>
            <button
              type="button"
              className={styles.chipIcon}
              aria-label={labels.zoomOut}
              onClick={() => cameraApi.current?.zoom(1 / 0.85)}
              data-action="zoom-out"
            >
              −
            </button>
            <button
              type="button"
              className={styles.chip}
              onClick={() => cameraApi.current?.reset()}
              data-action="reset"
            >
              {labels.reset}
            </button>
          </>
        ) : null}
      </div>

      {showing3D && colourName ? (
        <p className={styles.shownIn}>{fill(labels.shownIn, { colour: colourName })}</p>
      ) : null}

      {hintText && showing3D ? (
        <p className={styles.hint} aria-hidden="true">
          {hintText}
        </p>
      ) : null}

      <div className={styles.statusWrap} role="status" aria-live="polite">
        {status ? (
          <div className={styles.status} data-status={s.phase}>
            {loading ? (
              <span className={styles.bar} aria-hidden="true">
                <i ref={bar} />
              </span>
            ) : null}
            <span>{status}</span>
            {detailedErrors && s.errorMessage ? (
              <span className={styles.detail}>{s.errorMessage}</span>
            ) : null}
            {canRetry ? (
              <button type="button" className={styles.chip} onClick={tryAgain} data-action="retry">
                {labels.tryAgain}
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
