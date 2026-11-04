"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, setCsrfToken, type StaffSessionInfo } from "./api";

type State =
  | { status: "loading" }
  | { status: "signed-out" }
  | { status: "signed-in"; info: StaffSessionInfo };

interface SessionContextValue {
  state: State;
  refresh: () => Promise<void>;
  signedIn: (info: StaffSessionInfo) => void;
  signOut: () => Promise<void>;
  can: (permission: string) => boolean;
}

async function fetchSession(): Promise<StaffSessionInfo | null> {
  try {
    const { data, response } = await api.GET("/api/v1/staff/auth/session");
    return response.ok && data ? data : null;
  } catch {
    return null;
  }
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>({ status: "loading" });

  const signedIn = useCallback((info: StaffSessionInfo) => {
    setCsrfToken(info.csrf_token);
    setState({ status: "signed-in", info });
  }, []);

  const apply = useCallback(
    (info: StaffSessionInfo | null) => {
      if (info) signedIn(info);
      else {
        setCsrfToken(null);
        setState({ status: "signed-out" });
      }
    },
    [signedIn],
  );

  const refresh = useCallback(() => fetchSession().then(apply), [apply]);

  const signOut = useCallback(async () => {
    await api.POST("/api/v1/staff/auth/logout").catch(() => undefined);
    setCsrfToken(null);
    setState({ status: "signed-out" });
  }, []);

  useEffect(() => {
    let current = true;
    void fetchSession().then((info) => current && apply(info));
    // Re-check when the tab regains focus, so an expired or revoked session is noticed promptly.
    const onFocus = () => void refresh();
    window.addEventListener("focus", onFocus);
    return () => {
      current = false;
      window.removeEventListener("focus", onFocus);
    };
  }, [apply, refresh]);

  const value = useMemo<SessionContextValue>(
    () => ({
      state,
      refresh,
      signedIn,
      signOut,
      can: (permission) =>
        state.status === "signed-in" && state.info.permissions.includes(permission),
    }),
    [state, refresh, signedIn, signOut],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}
