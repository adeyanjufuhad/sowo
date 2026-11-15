// Small helpers for voice notes: picking a recording format, labels, and encoding for upload.

import type { VoiceStatus } from "@sowo/shared";

// shortcut: mirrors the API's VOICE_MAX_SECONDS default; read it from the API if a deployment changes it.
export const MAX_RECORD_SECONDS = 120;

// Chrome and Android record webm/opus, Firefox ogg/opus, iPhone Safari mp4. Whisper reads all of them.
const RECORDING_TYPES = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4", "audio/webm"];

/** The first format this browser can record, or undefined to let it choose. */
export function pickRecordingType(isSupported: (type: string) => boolean): string | undefined {
  return RECORDING_TYPES.find((type) => {
    try {
      return isSupported(type);
    } catch {
      return false;
    }
  });
}

/** 6400 -> "0:06", 65000 -> "1:05". */
export function formatDuration(ms: number): string {
  const seconds = Math.max(0, Math.round(ms / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

/** What to show under a voice note that has no transcript (yet). */
export function voiceStatusLabel(status: VoiceStatus): string | null {
  if (status === "PENDING") return "Listening…";
  if (status === "FAILED") return "Couldn't make this voice note out";
  if (status === "TOO_LONG") return "Too long to transcribe";
  return null;
}

/** A recording as base64, for the JSON upload. Chunked, so a long recording doesn't overflow the call stack. */
export async function blobToBase64(blob: Blob): Promise<string> {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(binary);
}
