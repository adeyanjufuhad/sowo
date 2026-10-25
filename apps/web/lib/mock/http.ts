import type { ApiError } from "@sowo/shared";
import { connection } from "next/server";
import { getMockState } from "./db";
import { MockError, type MockState } from "./store";

const CODES: Record<number, ApiError["error"]["code"]> = {
  400: "BAD_REQUEST",
  404: "NOT_FOUND",
  409: "CONFLICT",
  500: "INTERNAL",
};

function errorResponse(status: number, message: string): Response {
  const body: ApiError = { error: { code: CODES[status] ?? "INTERNAL", message } };
  return Response.json(body, { status });
}

/**
 * Runs a mock handler at request time (never prerendered: the store is mutable)
 * and maps MockError to the contract's error shape.
 */
export async function handle<T>(run: (state: MockState, now: Date) => T): Promise<Response> {
  await connection();
  try {
    return Response.json(run(getMockState(), new Date()));
  } catch (error) {
    if (error instanceof MockError) return errorResponse(error.status, error.message);
    console.error("[mock api]", error);
    return errorResponse(500, "Something went wrong in the mock API");
  }
}

/** Read a JSON body, turning malformed JSON into a 400. */
export async function readJson<T>(request: Request): Promise<T> {
  try {
    return (await request.json()) as T;
  } catch {
    throw new MockError(400, "Request body must be JSON");
  }
}

export async function handleWithBody<B, T>(
  request: Request,
  run: (state: MockState, body: B, now: Date) => T,
): Promise<Response> {
  let body: B;
  try {
    body = await readJson<B>(request);
  } catch (error) {
    return errorResponse(400, (error as Error).message);
  }
  return handle((state, now) => run(state, body, now));
}
