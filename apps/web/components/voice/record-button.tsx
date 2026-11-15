"use client";

import { Mic } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { cn } from "@/lib/utils";
import { formatDuration, MAX_RECORD_SECONDS, pickRecordingType } from "@/lib/voice";

const MIN_RECORDING_MS = 600; // shorter than this is a slipped thumb, not a voice note

/** Hold to record, let go to send. Space or Enter does the same from a keyboard. */
export function RecordButton({
  disabled,
  onRecorded,
  onError,
}: {
  disabled?: boolean;
  onRecorded: (audio: Blob, mimeType: string) => void;
  onError: (message: string) => void;
}) {
  const [recordingSince, setRecordingSince] = useState<number | null>(null);
  const [now, setNow] = useState(0);
  const recorder = useRef<MediaRecorder | null>(null);
  const held = useRef(false); // still pressed? The permission prompt can outlast a quick tap.
  const stopTimer = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (recordingSince === null) return;
    const tick = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(tick);
  }, [recordingSince]);

  useEffect(() => () => recorder.current?.stream.getTracks().forEach((t) => t.stop()), []);

  async function start() {
    if (disabled || recorder.current) return;
    held.current = true;
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      held.current = false;
      onError("Allow the microphone to send a voice note, or type your message.");
      return;
    }
    if (!held.current) {
      stream.getTracks().forEach((t) => t.stop()); // let go while the browser was asking for the mic
      return;
    }
    const mimeType = pickRecordingType((type) => MediaRecorder.isTypeSupported(type));
    const rec = new MediaRecorder(stream, { ...(mimeType ? { mimeType } : {}), audioBitsPerSecond: 32_000 });
    const chunks: Blob[] = [];
    const startedAt = Date.now();
    rec.ondataavailable = (event) => event.data.size && chunks.push(event.data);
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      recorder.current = null;
      setRecordingSince(null);
      window.clearTimeout(stopTimer.current);
      if (Date.now() - startedAt < MIN_RECORDING_MS) {
        onError("Hold the mic button while you talk, then let go to send.");
        return;
      }
      const type = rec.mimeType || mimeType || "audio/webm";
      onRecorded(new Blob(chunks, { type }), type);
    };
    recorder.current = rec;
    rec.start();
    setRecordingSince(startedAt);
    setNow(startedAt);
    stopTimer.current = window.setTimeout(stop, MAX_RECORD_SECONDS * 1000);
  }

  function stop() {
    held.current = false;
    if (recorder.current?.state === "recording") recorder.current.stop();
  }

  function onPointerDown(event: PointerEvent<HTMLButtonElement>) {
    event.currentTarget.setPointerCapture(event.pointerId); // a thumb that slides off still ends the recording
    void start();
  }

  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if ((event.key === " " || event.key === "Enter") && !event.repeat) {
      event.preventDefault();
      void start();
    }
  }

  function onKeyUp(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === " " || event.key === "Enter") stop();
  }

  const recording = recordingSince !== null;
  return (
    <>
      {recording ? (
        <span role="status" className="flex shrink-0 items-center gap-1.5 text-sm font-medium text-accent-strong tabular-nums">
          <span aria-hidden className="size-2 animate-pulse rounded-full bg-accent-strong" />
          {formatDuration(now - recordingSince)}
        </span>
      ) : null}
      <button
        type="button"
        disabled={disabled}
        aria-label="Hold to record a voice note"
        aria-pressed={recording}
        onPointerDown={onPointerDown}
        onPointerUp={stop}
        onPointerCancel={stop}
        onKeyDown={onKeyDown}
        onKeyUp={onKeyUp}
        onContextMenu={(event) => event.preventDefault()}
        className={cn(
          "grid size-11 shrink-0 touch-none place-items-center rounded-full ring-1 ring-line transition-[transform,background-color] select-none [-webkit-touch-callout:none] disabled:opacity-40",
          recording ? "scale-110 bg-accent-strong text-white ring-accent-strong" : "bg-paper text-ink hover:bg-accent-wash",
        )}
      >
        <Mic aria-hidden className="size-5" strokeWidth={2} />
      </button>
    </>
  );
}
