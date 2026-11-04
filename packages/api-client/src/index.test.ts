import { describe, expect, it, vi } from "vitest";
import { ApiError, createApiClient, isProblemDetails, unwrap } from "./index";

function jsonResponse(body: unknown, status = 200, contentType = "application/json"): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": contentType } });
}

describe("api client", () => {
  it("calls the typed API index endpoint and returns its data", async () => {
    const fetch = vi.fn(async (_input: Request) =>
      jsonResponse({ name: "AureVon API", version: "v1" }),
    );
    const client = createApiClient({ baseUrl: "http://api.test", fetch });
    const data = unwrap(await client.GET("/api/v1/"));
    expect(data).toEqual({ name: "AureVon API", version: "v1" });
    const request = fetch.mock.calls[0]![0];
    expect(request.url).toBe("http://api.test/api/v1/");
    expect(request.headers.get("Accept")).toBe("application/json");
  });

  it("turns problem details into an ApiError", async () => {
    const problem = {
      type: "about:blank",
      title: "Not found",
      status: 404,
      detail: "No API endpoint matches this path.",
    };
    const fetch = vi.fn(async () => jsonResponse(problem, 404, "application/problem+json"));
    const client = createApiClient({ baseUrl: "http://api.test", fetch });
    const call = client.GET("/api/v1/").then(unwrap);
    await expect(call).rejects.toBeInstanceOf(ApiError);
    await expect(call).rejects.toMatchObject({
      status: 404,
      problem,
      message: "Not found: No API endpoint matches this path.",
    });
  });

  it("still throws a useful error when the body is not problem details", async () => {
    const fetch = vi.fn(async () => new Response("Bad gateway", { status: 502 }));
    const client = createApiClient({ baseUrl: "http://api.test", fetch });
    await expect(client.GET("/api/v1/").then(unwrap)).rejects.toMatchObject({
      status: 502,
      problem: null,
      message: "HTTP 502",
    });
  });

  it("recognises problem details strictly", () => {
    expect(isProblemDetails({ type: "x", title: "y", status: 400 })).toBe(true);
    expect(isProblemDetails({ title: "y", status: 400 })).toBe(false);
    expect(isProblemDetails(null)).toBe(false);
  });
});
