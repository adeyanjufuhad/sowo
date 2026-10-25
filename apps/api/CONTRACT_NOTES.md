# Contract notes

## Stage 1 conversation persistence states

Stage 1 persists the explicitly requested `ACTIVE`, `NEEDS_ATTENTION`, and `PAUSED` states. The HTTP contract uses `AI_ACTIVE`, `NEEDS_ATTENTION`, `HUMAN_TAKEOVER`, and `CLOSED`. Before dashboard endpoints are added, define the API mapping (expected: `ACTIVE` to `AI_ACTIVE`, `PAUSED` to `HUMAN_TAKEOVER`) or migrate the stored enum.
