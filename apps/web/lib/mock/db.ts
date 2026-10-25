import { createSeedState } from "./seed";
import type { MockState } from "./store";

// Next can load each route handler as its own module instance, so the store lives
// on globalThis to be shared. It resets whenever the server restarts.
const globalForMock = globalThis as typeof globalThis & { __sowoMock?: MockState };

export function getMockState(): MockState {
  globalForMock.__sowoMock ??= createSeedState();
  return globalForMock.__sowoMock;
}
