import createClient, { type Client } from "openapi-fetch";
import type { paths } from "./schema";

export type { components, paths } from "./schema";

/** The API's single error shape: RFC 9457 problem details (MTS §8). */
export interface ProblemDetails {
  type: string;
  title: string;
  status: number;
  detail?: string;
  errors?: Record<string, unknown>;
}

export function isProblemDetails(value: unknown): value is ProblemDetails {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return typeof v.type === "string" && typeof v.title === "string" && typeof v.status === "number";
}

/** Thrown by `unwrap` for any non-2xx response, carrying the problem details when the API sent them. */
export class ApiError extends Error {
  readonly status: number;
  readonly problem: ProblemDetails | null;

  constructor(status: number, problem: ProblemDetails | null) {
    super(
      problem ? `${problem.title}${problem.detail ? `: ${problem.detail}` : ""}` : `HTTP ${status}`,
    );
    this.name = "ApiError";
    this.status = status;
    this.problem = problem;
  }
}

export type AureVonClient = Client<paths>;

export interface ClientOptions {
  /** Origin the API is served from, without a trailing slash. Empty string = same origin as the page. */
  baseUrl: string;
  /** openapi-fetch always calls fetch with a Request object. */
  fetch?: (input: Request) => Promise<Response>;
  headers?: Record<string, string>;
}

export function createApiClient({ baseUrl, fetch, headers }: ClientOptions): AureVonClient {
  return createClient<paths>({
    baseUrl,
    credentials: "same-origin",
    headers: { Accept: "application/json", ...headers },
    ...(fetch ? { fetch } : {}),
  });
}

/** Returns the data of a successful call, or throws ApiError. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.response.ok && result.data !== undefined) return result.data;
  throw new ApiError(result.response.status, isProblemDetails(result.error) ? result.error : null);
}
