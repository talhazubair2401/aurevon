"use client";

import { ApiError, createApiClient, isProblemDetails, type components } from "@aurevon/api-client";
import { useCallback, useEffect, useState, useSyncExternalStore } from "react";

export type Schemas = components["schemas"];
export type StaffSessionInfo = Schemas["StaffSessionInfoOut"];

/** The staff app calls only /api/v1/staff/… with the staff session (MTS §15 rules). */
export const api = createApiClient({ baseUrl: "" });

// The CSRF token comes from the session response and is kept in memory only (never in storage).
let csrfToken: string | null = null;
export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

api.use({
  onRequest({ request }) {
    if (csrfToken && request.method !== "GET") request.headers.set("X-CSRF-Token", csrfToken);
    return request;
  },
});

// Called when an action needs the authenticator code again (decision 0003, 2.5). Set by StepUpProvider.
let stepUpHandler: (() => Promise<boolean>) | null = null;
export function setStepUpHandler(handler: (() => Promise<boolean>) | null): void {
  stepUpHandler = handler;
}

type Result<T> = { data?: T; error?: unknown; response: Response };

/** Runs an API call; on `step-up-required` asks for a code once and retries. Throws ApiError otherwise. */
export async function call<T>(run: () => Promise<Result<T>>): Promise<T> {
  let result = await run();
  if (!result.response.ok && problemCode(result.error) === "step-up-required" && stepUpHandler) {
    if (await stepUpHandler()) result = await run();
  }
  if (result.response.ok) return result.data as T;
  throw new ApiError(result.response.status, isProblemDetails(result.error) ? result.error : null);
}

export function problemCode(error: unknown): string | null {
  if (!isProblemDetails(error)) return null;
  return error.type.split("/").pop() ?? null;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const fieldErrors = error.problem?.errors;
    if (fieldErrors && typeof fieldErrors === "object") {
      const first = Object.values(fieldErrors)[0];
      if (Array.isArray(first) && typeof first[0] === "string") return first[0];
    }
    return error.problem?.detail ?? error.problem?.title ?? "Something went wrong. Try again.";
  }
  return "We couldn't reach the server. Check your connection and try again.";
}

export function errorCode(error: unknown): string | null {
  return error instanceof ApiError ? problemCode(error.problem) : null;
}

/** Link tokens arrive in the URL fragment (#token=…), which never reaches servers or logs. */
export function tokenFromHash(): string {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "";
}

let capturedToken: string | null = null;
function captureToken(): string {
  if (capturedToken === null) {
    capturedToken = tokenFromHash();
    // The token stays in memory only: remove it from the address bar and history.
    if (capturedToken) window.history.replaceState(null, "", window.location.pathname);
  }
  return capturedToken;
}
const noSubscription = () => () => undefined;

/** The link token from #token=…, read once on the client (empty during server rendering). */
export function useHashToken(): { token: string; checked: boolean } {
  const token = useSyncExternalStore(noSubscription, captureToken, () => "");
  const checked = useSyncExternalStore(
    noSubscription,
    () => true,
    () => false,
  );
  return { token, checked };
}

/** Loads data from the API; state is only set in promise callbacks. `reload()` fetches again. */
export function useApiData<T>(fetcher: () => Promise<T>): {
  data: T | undefined;
  error: string | null;
  reload: () => void;
} {
  const [version, setVersion] = useState(0);
  const [state, setState] = useState<{ data: T | undefined; error: string | null }>({
    data: undefined,
    error: null,
  });
  useEffect(() => {
    let current = true;
    fetcher()
      .then((data) => current && setState({ data, error: null }))
      .catch((e: unknown) => current && setState((s) => ({ ...s, error: errorMessage(e) })));
    return () => {
      current = false;
    };
  }, [fetcher, version]);
  const reload = useCallback(() => setVersion((v) => v + 1), []);
  return { ...state, reload };
}

export const ROLE_OPTIONS = [
  { code: "owner", name: "Owner" },
  { code: "store_admin", name: "Store Admin" },
  { code: "accountant", name: "Accountant" },
  { code: "inventory_manager", name: "Inventory Manager" },
  { code: "support", name: "Support" },
  { code: "content_marketing", name: "Content / Marketing" },
] as const;

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("en-PK", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Karachi",
  }).format(new Date(iso));
}
