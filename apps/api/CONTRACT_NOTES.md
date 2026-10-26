# Contract notes

## Stage 1 conversation persistence states

Stage 1 persists the explicitly requested `ACTIVE`, `NEEDS_ATTENTION`, and `PAUSED` states. The HTTP contract uses `AI_ACTIVE`, `NEEDS_ATTENTION`, `HUMAN_TAKEOVER`, and `CLOSED`. Before dashboard endpoints are added, define the API mapping (expected: `ACTIVE` to `AI_ACTIVE`, `PAUSED` to `HUMAN_TAKEOVER`) or migrate the stored enum.

Stage 4 keeps the requested storage transitions (`PAUSED` plus `ai_paused`, then `ACTIVE`) and serializes them to the API contract's `HUMAN_TAKEOVER` and `AI_ACTIVE` statuses. `NEEDS_ATTENTION` maps directly. The storage enum has no `CLOSED` value yet.

## Stage 4 tool-call shape

The Stage 4 wording calls the tool-call field `name`, while the shared TypeScript contract defines it as `tool`. Dashboard responses follow the shared contract: `tool`, `input`, and `output`.
