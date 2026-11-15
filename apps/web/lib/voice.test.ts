import { describe, expect, it } from "vitest";
import { blobToBase64, formatDuration, pickRecordingType, voiceStatusLabel } from "./voice";

describe("pickRecordingType", () => {
  it("prefers opus in webm (Chrome, Android)", () => {
    expect(pickRecordingType(() => true)).toBe("audio/webm;codecs=opus");
  });

  it("falls back to mp4 on iPhone Safari", () => {
    expect(pickRecordingType((type) => type === "audio/mp4")).toBe("audio/mp4");
  });

  it("lets the browser choose when it supports none, or the check throws", () => {
    expect(pickRecordingType(() => false)).toBeUndefined();
    expect(
      pickRecordingType(() => {
        throw new Error("old browser");
      }),
    ).toBeUndefined();
  });
});

describe("formatDuration", () => {
  it.each([
    [0, "0:00"],
    [6400, "0:06"],
    [65000, "1:05"],
    [120000, "2:00"],
    [-5, "0:00"],
  ])("%d ms is %s", (ms, label) => {
    expect(formatDuration(ms)).toBe(label);
  });
});

describe("voiceStatusLabel", () => {
  it("says nothing once there is a transcript", () => {
    expect(voiceStatusLabel("TRANSCRIBED")).toBeNull();
    expect(voiceStatusLabel("FAILED")).toMatch(/couldn't/i);
    expect(voiceStatusLabel("TOO_LONG")).toMatch(/too long/i);
  });
});

describe("blobToBase64", () => {
  it("encodes bytes exactly, including big recordings", async () => {
    expect(await blobToBase64(new Blob([new Uint8Array([0, 1, 254, 255])]))).toBe("AAH+/w==");
    const big = new Uint8Array(100_000).map((_, i) => i % 256);
    const decoded = Uint8Array.from(atob(await blobToBase64(new Blob([big]))), (c) => c.charCodeAt(0));
    expect(decoded).toEqual(big);
  });
});
