// The mock backend running inside the visitor's browser, saved to localStorage.
// Each visitor gets a private sandbox that survives reloads and is shared between
// tabs, so a sale made on /try shows up on /dashboard. Serverless hosts can't do
// that with in-memory state: requests may land on different instances.

import { ApiRequestError } from "../api-error";
import { createSeedState } from "./seed";
import {
  MockError,
  deserializeState,
  serializeState,
  type MockState,
  type SerializedMockState,
} from "./store";

const STORAGE_KEY = "sowo.mock.v1";

// Fallback when storage is unavailable (private mode, blocked site data).
let memoryCopy: MockState | null = null;

function load(): MockState {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) return deserializeState(JSON.parse(raw) as SerializedMockState);
  } catch {
    // fall through to the in-memory copy
  }
  memoryCopy ??= createSeedState(new Date());
  return memoryCopy;
}

function save(state: MockState) {
  memoryCopy = state;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(serializeState(state)));
  } catch {
    // keep working from memory
  }
}

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Run one mock operation against fresh state from storage, save the result and
 * return a deep copy, as an HTTP round trip would. `latencyMs` makes replies feel real.
 */
export async function runLocal<T>(operation: (state: MockState, now: Date) => T, latencyMs = 0): Promise<T> {
  if (latencyMs) await wait(latencyMs);
  const state = load();
  try {
    const result = operation(state, new Date());
    save(state);
    return structuredClone(result);
  } catch (error) {
    if (error instanceof MockError) throw new ApiRequestError(error.status, error.message);
    throw error;
  }
}

/** Wipe the sandbox; the next call starts again from the seeded data. */
export function resetLocalMock() {
  memoryCopy = null;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // nothing stored
  }
}
