# Contract notes

## Stage 1 conversation persistence states

Stage 1 persists the explicitly requested `ACTIVE`, `NEEDS_ATTENTION`, and `PAUSED` states. The HTTP contract uses `AI_ACTIVE`, `NEEDS_ATTENTION`, `HUMAN_TAKEOVER`, and `CLOSED`. Before dashboard endpoints are added, define the API mapping (expected: `ACTIVE` to `AI_ACTIVE`, `PAUSED` to `HUMAN_TAKEOVER`) or migrate the stored enum.

Stage 4 keeps the requested storage transitions (`PAUSED` plus `ai_paused`, then `ACTIVE`) and serializes them to the API contract's `HUMAN_TAKEOVER` and `AI_ACTIVE` statuses. `NEEDS_ATTENTION` maps directly. The storage enum has no `CLOSED` value yet.

## Stage 4 tool-call shape

The Stage 4 wording calls the tool-call field `name`, while the shared TypeScript contract defines it as `tool`. Dashboard responses follow the shared contract: `tool`, `input`, and `output`.

## Stage 5: the agent, WhatsApp, Paystack and the simulator

`POST /simulator/messages` and `POST /simulator/payments` are implemented as in the contract, plus a `SIMULATOR_ENABLED` switch (default on) to turn both off for a deployment that serves real buyers. `/simulator/payments` only ever touches orders of simulator conversations, never a real buyer's.

Where the real backend differs from, or adds to, `docs/api-contract.md` (for its owner to fold in):

- **`evaluate_offer` decisions.** The haggling engine returns `ACCEPT`, `COUNTER`, `REJECT` (offer under half the list price) and `HANDOFF` (repeated offers below the floor), not `HOLD`. `REJECT` and `HANDOFF` carry no price. The shared type `OfferDecision` now includes both.
- **`sku` in tool inputs.** `evaluate_offer` and `get_quote` inputs also carry an optional `sku` (the readable form of `productId`), so the dashboard can show `LOAF-BLK-43` instead of a UUID. `search_catalog` hits include `sku`, as the contract already says.
- **`escalate_to_vendor` is not traced.** The model has a fifth tool for hand-offs, but it is not written to `toolCalls`, because the contract and the web app only know four tools. A hand-off shows as the conversation's `NEEDS_ATTENTION` status. `HANDOFF` from `evaluate_offer` is traced as normal.
- **Ids.** Orders, conversations, messages and products have UUID ids (the web mock used `ord_1043` style ids). `quoteId` is `q_` plus eight hex characters. The readable order handle is `paymentReference` (`SW-…`), and the dashboard should show that rather than `id`.
- **`paymentUrl`.** For WhatsApp buyers it is Paystack's `authorization_url`. For simulator chats it is the placeholder `https://paystack.test/pay/<reference>`. If Paystack is not configured or is down, no order is left behind: `request_payment` fails, the held stock is released and the chat goes to the vendor.
- **Order status.** Orders store `PENDING`, `PAID`, `EXPIRED` and `CANCELLED`. The API shows `PAID` as `PAID`, `EXPIRED` and `CANCELLED` as `FAILED`, and the rest as `PENDING`. `REFUNDED` is never produced.
- **Fulfilment.** Paid orders report `PACKAGING`. There is no way yet to move an order to `SHIPPED` or `DELIVERED`.
- **Conversation `CLOSED`** is still never produced.

New tables: `quotes` (a priced basket the model was shown; `request_payment` turns one into an order). Existing databases get it from `create_all` on startup.
