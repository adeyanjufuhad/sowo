"use client";

import type { MessageVoice } from "@sowo/shared";
import { LoaderCircle, Mic, Pause, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { fetchVoiceAudio } from "@/lib/api";
import { cn } from "@/lib/utils";
import { formatDuration, voiceStatusLabel } from "@/lib/voice";

/** The top of a voice-note bubble: play button, length, and what happened to it. The transcript is the message body. */
export function VoiceNote({
  voice,
  conversationId,
  messageId,
  simulator,
  onAccent = false,
}: {
  voice: MessageVoice;
  conversationId: string;
  messageId: string;
  simulator: boolean;
  /** Inside a dark (accent) bubble, as on /try. */
  onAccent?: boolean;
}) {
  const [state, setState] = useState<"idle" | "loading" | "playing" | "error">("idle");
  const audio = useRef<HTMLAudioElement | null>(null);
  const url = useRef<string | null>(null);

  useEffect(
    () => () => {
      audio.current?.pause();
      if (url.current) URL.revokeObjectURL(url.current);
    },
    [],
  );

  async function toggle() {
    if (state === "playing") {
      audio.current?.pause();
      setState("idle");
      return;
    }
    try {
      if (!audio.current) {
        setState("loading");
        url.current = URL.createObjectURL(await fetchVoiceAudio(conversationId, messageId, simulator));
        audio.current = new Audio(url.current);
        audio.current.onended = () => setState("idle");
      }
      await audio.current.play();
      setState("playing");
    } catch {
      setState("error"); // e.g. an older iPhone can't play WhatsApp's OGG; the transcript still shows
    }
  }

  const label = voiceStatusLabel(voice.status);
  const Icon = state === "playing" ? Pause : state === "loading" ? LoaderCircle : Play;
  const quiet = onAccent ? "text-white/80" : "text-muted";
  return (
    <span className="mb-1 flex flex-col gap-0.5">
      <span className="flex items-center gap-2">
        {voice.hasAudio ? (
          <button
            type="button"
            onClick={toggle}
            disabled={state === "loading"}
            aria-label={state === "playing" ? "Pause voice note" : "Play voice note"}
            className={cn(
              "grid size-8 shrink-0 place-items-center rounded-full transition-transform active:scale-95 disabled:opacity-60",
              onAccent ? "bg-white text-accent-strong" : "bg-accent-strong text-white",
            )}
          >
            <Icon aria-hidden className={cn("size-4", state === "loading" && "animate-spin")} strokeWidth={2} />
          </button>
        ) : (
          <Mic aria-hidden className={cn("size-4", quiet)} strokeWidth={1.75} />
        )}
        <span className={cn("text-xs font-medium", quiet)}>
          Voice note{voice.durationMs ? ` · ${formatDuration(voice.durationMs)}` : ""}
        </span>
      </span>
      {label ? <span className={cn("text-xs italic", quiet)}>{label}</span> : null}
      {state === "error" ? (
        <span className={cn("text-xs", quiet)}>This browser can&apos;t play it. The transcript is below.</span>
      ) : null}
    </span>
  );
}
