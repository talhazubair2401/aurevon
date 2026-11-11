"use client";

/**
 * Homepage hero garment (redesign, 11 Nov 2026). The poster (a photograph of the same garment) renders on the
 * server and stays until the live model is ready; then it cross-fades to 3D. The 3D code is fetched only when
 * the hero is on screen, the browser has WebGL, the person hasn't asked for reduced motion or data saving, and
 * the device reports enough memory. Any failure keeps the poster: the hero never shows an error.
 *
 * The 3D canvas is decorative (the poster's alt text describes the garment); drag turns it ±30° on a mouse or
 * trackpad and springs back. Release safeguards are upstream: the storefront only passes a model when the
 * catalogue returns one, which it does only while THREED_FOR_SHOPPERS is on (V-01 to V-03).
 */
import { type ComponentType, type ReactNode, useEffect, useRef, useState } from "react";
import styles from "./hero.module.css";

export interface HeroViewerProps {
  src: string;
  decoderPath: string;
  /** Material variant (colour slug); "" shows the model as delivered. */
  variant?: string;
  /** Shown to assistive technology while the model loads; the canvas itself is decorative. */
  loadingLabel: string;
  className?: string | undefined;
  /** The poster photograph, rendered on the server. */
  children: ReactNode;
}

export interface HeroSceneProps {
  src: string;
  decoderPath: string;
  variant: string;
  active: boolean;
  draggable: boolean;
  onReady: () => void;
  onFail: (error: unknown) => void;
}

type Phase = "poster" | "loading" | "ready";

function capable(): boolean {
  if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return false;
  const nav = navigator as Navigator & {
    connection?: { saveData?: boolean };
    deviceMemory?: number;
  };
  if (nav.connection?.saveData) return false;
  if (typeof nav.deviceMemory === "number" && nav.deviceMemory < 4) return false;
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") ?? canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

export function HeroViewer({
  src,
  decoderPath,
  variant = "",
  loadingLabel,
  className,
  children,
}: HeroViewerProps) {
  const root = useRef<HTMLDivElement>(null);
  const [phase, setPhase] = useState<Phase>("poster");
  const [Scene, setScene] = useState<ComponentType<HeroSceneProps> | null>(null);
  const [onScreen, setOnScreen] = useState(false);
  const [pageVisible, setPageVisible] = useState(true);
  const [draggable, setDraggable] = useState(false);

  useEffect(() => {
    const el = root.current;
    const onVisibility = () => setPageVisible(document.visibilityState !== "hidden");
    document.addEventListener("visibilitychange", onVisibility);
    let observer: IntersectionObserver | undefined;
    if (el && typeof IntersectionObserver !== "undefined") {
      observer = new IntersectionObserver(
        ([entry]) => setOnScreen(Boolean(entry?.isIntersecting)),
        {
          threshold: 0.05,
        },
      );
      observer.observe(el);
    }
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      observer?.disconnect();
    };
  }, []);

  // Fetch the 3D code once, the first time the hero is on screen, after the page has painted.
  useEffect(() => {
    if (!onScreen || phase !== "poster" || Scene) return;
    if (!capable()) return;
    setDraggable(window.matchMedia?.("(pointer: fine)").matches ?? false);
    let cancelled = false;
    const start = () =>
      import("./HeroScene")
        .then((m) => {
          if (cancelled) return;
          setScene(() => m.default);
          setPhase("loading");
        })
        .catch((error: unknown) => console.warn("[viewer3d] hero 3D code failed to load:", error));
    const idle = (
      window as Window & {
        requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number;
      }
    ).requestIdleCallback;
    if (idle) idle(start, { timeout: 2000 });
    else setTimeout(start, 300);
    return () => {
      cancelled = true;
    };
  }, [onScreen, phase, Scene]);

  return (
    <div
      ref={root}
      className={[styles.hero, className ?? ""].filter(Boolean).join(" ")}
      data-phase={phase}
      aria-busy={phase === "loading"}
    >
      <div className={styles.poster}>{children}</div>
      {Scene && phase !== "poster" ? (
        <div className={styles.canvas} aria-hidden="true">
          <Scene
            src={src}
            decoderPath={decoderPath}
            variant={variant}
            active={onScreen && pageVisible}
            draggable={draggable}
            onReady={() => setPhase("ready")}
            onFail={(error) => {
              console.warn("[viewer3d] hero model failed; keeping the photograph:", error);
              setScene(null);
              setPhase("poster");
            }}
          />
        </div>
      ) : null}
      {phase === "loading" ? (
        <span className={styles.progress} role="status">
          <span className={styles.srOnly}>{loadingLabel}</span>
        </span>
      ) : null}
    </div>
  );
}
