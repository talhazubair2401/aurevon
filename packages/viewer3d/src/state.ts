/**
 * Viewer state, kept outside React (MTS §4 `ViewerState`): the poster, status messages and the rest of the
 * page keep working even if the 3D code never loads. Carries over the P-09 v2 behaviour:
 * - no fixed timeout: slow loads only change the message; failure is declared only for real errors (D4)
 * - 3D takes over whenever it is ready, and "Show 3D" appears once it is (D2)
 * - rendering only while 3D is showing, on screen and in a visible tab (D3)
 */

export type Phase = "loading" | "ready" | "failed" | "unavailable" | "lost";
export type FailureKind = "libraries" | "model";

export interface ViewerSnapshot {
  phase: Phase;
  /** The shopper asked for the image instead of 3D. */
  userChoseImage: boolean;
  /** The selected colour has a 3D version (decision 0007, D-03); otherwise its photos show. */
  colourHas3D: boolean;
  canvasMounted: boolean;
  visible: boolean;
  pageVisible: boolean;
  autoRotate: boolean;
  /** 0 normal, 1 still loading, 2 slow connection (message only, never a failure). */
  slow: 0 | 1 | 2;
  progress: number;
  attempt: number;
  failure: FailureKind | null;
  /** Machine-readable reason, for staff previews and tests. */
  errorCode: string | null;
  errorMessage: string | null;
}

export type Listener = () => void;

export class ViewerStore {
  private state: ViewerSnapshot;
  private listeners = new Set<Listener>();

  constructor(initial: Partial<ViewerSnapshot> = {}) {
    this.state = {
      phase: "loading",
      userChoseImage: false,
      colourHas3D: true,
      canvasMounted: false,
      visible: true,
      pageVisible: true,
      autoRotate: true,
      slow: 0,
      progress: 0,
      attempt: 0,
      failure: null,
      errorCode: null,
      errorMessage: null,
      ...initial,
    };
  }

  get = (): ViewerSnapshot => this.state;

  set(patch: Partial<ViewerSnapshot>): void {
    const next = { ...this.state, ...patch };
    if (
      Object.keys(patch).every((k) =>
        Object.is(next[k as keyof ViewerSnapshot], this.state[k as keyof ViewerSnapshot]),
      )
    )
      return;
    this.state = next;
    this.listeners.forEach((f) => f());
  }

  subscribe = (f: Listener): (() => void) => {
    this.listeners.add(f);
    return () => this.listeners.delete(f);
  };

  fail(failure: FailureKind, code: string, message: string): void {
    this.set({ phase: "failed", failure, errorCode: code, errorMessage: message });
  }
}

/** 3D is what the shopper sees right now. */
export function is3D(s: ViewerSnapshot): boolean {
  return s.phase === "ready" && !s.userChoseImage && s.colourHas3D;
}

/** Render only when 3D is on screen (D3). During warm-up it renders under the poster so the first frame is ready. */
export function shouldRender(s: ViewerSnapshot): boolean {
  return s.canvasMounted && s.pageVisible && s.visible && (s.phase === "loading" || is3D(s));
}

/** Messages change with time while loading (D4): about 8 s, then 25 s. */
export const SLOW_AFTER_MS = [8000, 25000] as const;
