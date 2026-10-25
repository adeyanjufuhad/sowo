"use client";

import { useEffect, useRef, useState } from "react";

/*
  Isometric "engine" drawing: a line-drawn puck with the Sowo mark in its well.
  A terracotta tape carries a real haggle in from the top left, wraps the puck and
  leaves as a paid order; a short tape rises out of the well carrying the floor
  price, which never leaves the server. Text scrolls along the tape when motion
  is allowed; otherwise it renders still.
*/

const CX = 500;
const RX = 215;
const RY = 92;
const TOP = 250; // centre of the top face
const SIDE = 46; // puck thickness

// Main tape: in from the top left, down the puck's left edge, round the front
// of its side wall, then off to the right along the tangent where it leaves.
const BAND = TOP + SIDE / 2;
const LEAVE = Math.PI / 3; // leaves the wall 60° past the leftmost point
const leaveX = CX + RX * Math.cos(LEAVE);
const leaveY = BAND + RY * Math.sin(LEAVE);
const slope = -(RY * Math.cos(LEAVE)) / (RX * Math.sin(LEAVE));
const MAIN_TAPE = [
  `M -40 10 C 140 90, ${CX - RX} ${BAND - 110}, ${CX - RX} ${BAND}`,
  `A ${RX} ${RY} 0 0 0 ${leaveX.toFixed(1)} ${leaveY.toFixed(1)}`,
  `L 1060 ${(leaveY + slope * (1060 - leaveX)).toFixed(1)}`,
].join(" ");
// Short tape rising out of the well.
const STUB_TAPE = `M ${CX + 40} ${TOP + 8} L ${CX + 128} 26`;

const MAIN_TEXT =
  "abeg do am 35k → evaluate_offer → counter ₦43,000    ·    make it 41 na → accept ₦41,000    ·    i dey ikeja → get_quote → ₦43,500    ·    paystack webhook → PAID    ·    ";
const STUB_TEXT = "floor price · stays on the server";

export function EngineIllustration() {
  const textRef = useRef<SVGTextElement>(null);
  const [loop, setLoop] = useState<number | null>(null);

  // Measure one copy of the text so the scroll loops seamlessly; skip with reduced motion.
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const text = textRef.current;
    if (!text) return;
    const id = requestAnimationFrame(() => setLoop(text.getComputedTextLength() / 3));
    return () => cancelAnimationFrame(id);
  }, []);

  return (
    <svg
      viewBox="0 0 1000 430"
      role="img"
      aria-label="A buyer's haggle flowing through Sowo's engine and coming out as a paid order, while the floor price stays on the server"
      className="h-auto w-full overflow-visible"
    >
      <defs>
        <path id="engine-main" d={MAIN_TAPE} />
        <path id="engine-stub" d={STUB_TAPE} />
        <clipPath id="engine-stage">
          <rect x="0" y="0" width="1000" height="430" />
        </clipPath>
      </defs>

      <g clipPath="url(#engine-stage)">
        {/* Base plate: a faint ring the puck sits on */}
        <ellipse cx={CX} cy={TOP + SIDE + 14} rx={RX + 34} ry={RY + 16} className="fill-none stroke-ink/15" strokeWidth={1.2} />

        {/* Puck side wall */}
        <path
          d={`M ${CX - RX} ${TOP} L ${CX - RX} ${TOP + SIDE} A ${RX} ${RY} 0 0 0 ${CX + RX} ${TOP + SIDE} L ${CX + RX} ${TOP}`}
          className="fill-paper-deep stroke-ink"
          strokeWidth={1.5}
          strokeLinejoin="round"
        />
        <path
          d={`M ${CX - RX} ${TOP + SIDE - 12} A ${RX} ${RY} 0 0 0 ${CX + RX} ${TOP + SIDE - 12}`}
          className="fill-none stroke-ink/30"
          strokeWidth={1}
        />

        {/* Top face, inner ring and well */}
        <ellipse cx={CX} cy={TOP} rx={RX} ry={RY} className="fill-card stroke-ink" strokeWidth={1.5} />
        <ellipse cx={CX} cy={TOP} rx={RX - 42} ry={RY - 18} className="fill-none stroke-ink/40" strokeWidth={1} />
        <ellipse cx={CX} cy={TOP + 4} rx={96} ry={40} className="fill-paper stroke-ink" strokeWidth={1.3} />
        <path d={`M ${CX - 96} ${TOP + 4} A 96 40 0 0 1 ${CX + 96} ${TOP + 4}`} className="fill-none stroke-ink/25" strokeWidth={7} />

        {/* Sowo mark lying flat in the well */}
        <g transform={`translate(${CX - 88} ${TOP - 14}) scale(2.6 1.1)`}>
          <path
            d="M16 3.5c7.2 0 12.5 4.9 12.5 11.2 0 6.3-5.3 11.2-12.5 11.2-1.4 0-2.7-.2-4-.5L6 28.5l1.6-5.4C5 21 3.5 18 3.5 14.7 3.5 8.4 8.8 3.5 16 3.5Z"
            className="fill-accent"
          />
        </g>

        {/* Rising tape: the floor price */}
        <use href="#engine-stub" className="fill-none stroke-accent" strokeWidth={26} strokeLinecap="round" />
        <text className="fill-white font-mono" fontSize={12} letterSpacing={0.6} dy={4}>
          <textPath href="#engine-stub" startOffset="10%">
            {STUB_TEXT}
          </textPath>
        </text>

        {/* Main tape: the haggle in, the paid order out */}
        <use href="#engine-main" className="fill-none stroke-accent" strokeWidth={28} strokeLinecap="round" />
        <text ref={textRef} className="fill-white font-mono" fontSize={13} letterSpacing={0.6} dy={4.5}>
          <textPath href="#engine-main">
            {MAIN_TEXT.repeat(3)}
            {loop ? (
              <animate attributeName="startOffset" from={-loop} to={0} dur="28s" repeatCount="indefinite" />
            ) : null}
          </textPath>
        </text>
      </g>
    </svg>
  );
}
