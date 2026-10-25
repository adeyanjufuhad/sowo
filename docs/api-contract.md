# Sowo API contract

This is the HTTP API that `apps/web` calls and `apps/api` implements. The TypeScript source of truth is [`packages/shared/src/api.ts`](../packages/shared/src/api.ts). If this document and that file disagree, the file wins; fix whichever is wrong in the same PR.

`apps/web` ships a mock of this whole contract at `/api/mock`, so the frontend works offline. Set `NEXT_PUBLIC_API_URL` to switch it to the real backend.

## Ground rules

| Rule | Detail |
| --- | --- |
| Money | Integer **kobo** everywhere (`₦1 = 100`). `4350000` is ₦43,500. No floats, no naira amounts on the wire. |
| Time | ISO 8601 strings in UTC: `"2026-10-25T19:42:00.000Z"`. |
| Who decides | The model phrases replies and picks tools. The **server** computes every tool `output`: prices, counters, totals, stock. A tool `input` never carries a price the server would trust, except the buyer's offer passed to `evaluate_offer`. |
| Floor price | `floorPriceKobo` appears only in `GET /products` (the vendor dashboard). It must never appear in a tool input or output, a message body, or the model's context. |
| JSON | Requests and responses are `application/json`. Lists are wrapped in an object (`{ "orders": [...] }`) so fields can be added later. |
| Ordering | Lists are newest first, except messages, which are oldest first. |
| CORS | The web app runs on `http://localhost:3000` in development; allow that origin. |

## Types

```ts
type ConversationStatus = "AI_ACTIVE" | "NEEDS_ATTENTION" | "HUMAN_TAKEOVER" | "CLOSED";

interface Conversation {
  id: string;
  customerName: string;
  platform: "WHATSAPP" | "SIMULATOR";
  status: ConversationStatus;
  lastMessageAt: string;      // ISO 8601
  preview: string;            // latest message text, for the chats list
}

interface Message {
  id: string;
  conversationId: string;
  sender: "BUYER" | "AI" | "VENDOR";
  body: string;
  createdAt: string;
  toolCalls?: ToolCall[];     // AI messages only, in the order they ran
}

interface Product {
  id: string;
  sku: string;
  name: string;
  basePriceKobo: number;
  floorPriceKobo: number;     // vendor-only
  stockOnHand: number;
  imageUrl: string;
}

interface Order {
  id: string;
  customerName: string;
  items: { productId: string; sku: string; name: string; quantity: number; unitPriceKobo: number }[];
  deliveryFeeKobo: number;
  totalKobo: number;          // item lines + delivery
  paymentStatus: "PENDING" | "PAID" | "FAILED" | "REFUNDED";
  fulfillmentStatus: "UNFULFILLED" | "PACKAGING" | "SHIPPED" | "DELIVERED";
  createdAt: string;
  conversationId?: string;    // optional extras
  deliveryArea?: string;
  paymentReference?: string;
}
```

### Conversation status

| Status | Meaning | Set by |
| --- | --- | --- |
| `AI_ACTIVE` | Sowo replies to the buyer. | Default; `POST /resume`. |
| `NEEDS_ATTENTION` | Sowo couldn't handle the message (complaint, exchange, custom request) and has stopped replying until the vendor looks. The dashboard highlights it. | Server. |
| `HUMAN_TAKEOVER` | The vendor is talking; Sowo stays quiet. | `POST /pause`, or any vendor reply. |
| `CLOSED` | Sale finished or conversation archived. A new buyer message reopens it as `AI_ACTIVE`. | Server. |

Sowo replies to the buyer only while the status is `AI_ACTIVE`.

## Tool calls

Each AI message carries the tools that produced it. `input` is what the model chose; `output` is what the server computed. The `/try` page shows both side by side so judges can see the split.

### `search_catalog`

```json
{
  "tool": "search_catalog",
  "input": { "query": "black loafers size 43" },
  "output": {
    "results": [
      { "productId": "prod_loafer_blk_43", "sku": "LOAF-BLK-43", "name": "Black Leather Loafers, size 43", "priceKobo": 4500000, "stockOnHand": 3 }
    ]
  }
}
```

### `evaluate_offer`

The buyer offered ₦35,000. The floor is ₦40,000, so the server counters. The floor itself is not in the output.

```json
{
  "tool": "evaluate_offer",
  "input": { "productId": "prod_loafer_blk_43", "offerKobo": 3500000 },
  "output": { "decision": "COUNTER", "counterKobo": 4300000 }
}
```

| `decision` | When | Extra field |
| --- | --- | --- |
| `ACCEPT` | Offer ≥ floor. The agreed price is `min(offer, basePrice)`. | `agreedPriceKobo` |
| `COUNTER` | Offer < floor and the server still has room to come down. | `counterKobo` |
| `HOLD` | Offer < floor and the counter has already reached the floor. | `counterKobo` (the final price) |

The mock's counter schedule, for reference (the real engine may differ): the gap between base and floor is conceded in steps of 40%, 70% and 100%, rounded to the nearest ₦500, and a counter never goes below the floor or above the previous counter. For the loafers (₦45,000 base, ₦40,000 floor) the first counter is ₦43,000.

### `get_quote`

The input has no prices. The server looks up the agreed price from the negotiation in this conversation and the delivery fee for the area.

```json
{
  "tool": "get_quote",
  "input": { "items": [{ "productId": "prod_loafer_blk_43", "quantity": 1 }], "deliveryArea": "Ikeja" },
  "output": {
    "quoteId": "q_7f3k",
    "lines": [{ "productId": "prod_loafer_blk_43", "name": "Black Leather Loafers, size 43", "quantity": 1, "unitPriceKobo": 4100000, "lineTotalKobo": 4100000 }],
    "subtotalKobo": 4100000,
    "deliveryArea": "Ikeja",
    "deliveryFeeKobo": 250000,
    "totalKobo": 4350000
  }
}
```

### `request_payment`

Creates a `PENDING` order and a Paystack test-mode payment link for a quote. Stock is reserved here and released if payment fails.

```json
{
  "tool": "request_payment",
  "input": { "quoteId": "q_7f3k" },
  "output": { "orderId": "ord_1042", "reference": "SW-1042-7F3K", "amountKobo": 4350000, "paymentUrl": "https://checkout.paystack.com/…" }
}
```

When Paystack's webhook confirms the charge (signature verified and amount checked against the order), the server marks the order `PAID`, moves fulfilment to `PACKAGING`, sends the buyer a receipt message, and alerts the vendor to pack. A buyer's screenshot of a transfer is never treated as payment.

## Endpoints

All paths are relative to the API base URL (`NEXT_PUBLIC_API_URL`, or `/api/mock`).

### `GET /conversations`

```json
{ "conversations": [Conversation, …] }
```

Newest `lastMessageAt` first. The dashboard polls this every 3 seconds.

### `GET /conversations/:id/messages`

```json
{ "conversation": Conversation, "messages": [Message, …] }
```

Oldest first. `404` if the conversation doesn't exist.

### `POST /conversations/:id/pause`

No body. Sets status to `HUMAN_TAKEOVER`. Returns `{ "conversation": Conversation }`. Pausing an already-paused conversation is not an error.

### `POST /conversations/:id/resume`

No body. Sets status to `AI_ACTIVE` (this also clears `NEEDS_ATTENTION`). Returns `{ "conversation": Conversation }`.

### `POST /conversations/:id/messages`

The vendor replies from the dashboard.

```json
// request
{ "body": "Hi Funke, this is Ada. I'll swap the size for you." }
// response
{ "conversation": Conversation, "message": Message }
```

The message has `sender: "VENDOR"`, and the conversation moves to `HUMAN_TAKEOVER` so Sowo doesn't talk over the vendor. `400` if `body` is empty.

### `GET /orders`

```json
{ "orders": [Order, …] }
```

### `GET /products`

```json
{ "products": [Product, …] }
```

Includes `floorPriceKobo`. This endpoint is for the vendor dashboard only and must not be exposed to buyers or the model.

### `POST /simulator/messages`

Sends a message as a buyer from the `/try` page and runs Sowo exactly as a WhatsApp message would.

```json
// request
{ "conversationId": "conv_abc", "body": "Abeg do am 35k" }
// response
{
  "conversation": Conversation,
  "messages": [
    { "id": "msg_1", "sender": "BUYER", "body": "Abeg do am 35k", … },
    { "id": "msg_2", "sender": "AI", "body": "35k too low for this one o…", "toolCalls": [{ "tool": "evaluate_offer", … }], … }
  ]
}
```

Omit `conversationId` to start a new conversation (`platform: "SIMULATOR"`, `customerName` defaults to `"Demo buyer"`). If the conversation isn't `AI_ACTIVE`, the buyer's message is stored and `messages` contains only that message.

### `POST /simulator/payments`

A demo helper that stands in for the Paystack webhook so the simulator can finish a sale offline.

```json
// request
{ "reference": "SW-1042-7F3K", "outcome": "SUCCESS" }
// response
{ "order": Order, "messages": [Message, …] }
```

`SUCCESS` marks the order `PAID` and `PACKAGING` and returns the receipt message; `FAILED` marks it `FAILED` and returns a retry message. `404` for an unknown reference, `409` if the order is no longer `PENDING`.

The real backend can implement this by feeding a test event through its own webhook handler, or not implement it at all once the `/try` page uses the real Paystack test checkout.

## Errors

Any non-2xx response has this body:

```json
{ "error": { "code": "NOT_FOUND", "message": "Conversation conv_x not found" } }
```

| HTTP | `code` |
| --- | --- |
| 400 | `BAD_REQUEST` |
| 404 | `NOT_FOUND` |
| 409 | `CONFLICT` |
| 500 | `INTERNAL` |

## Open questions for the backend

- **Escalation.** How does a conversation reach `NEEDS_ATTENTION`? One option is a fifth tool, `escalate_to_vendor`, that the model calls when it's out of its depth. The mock escalates any message it can't match.
- **Delivery areas.** The mock uses a fixed fee table (Ikeja ₦2,500, Yaba ₦2,000, Lekki ₦3,500, …). The real list should come from vendor settings.
- **Auth.** The dashboard has no login for the hackathon. If the backend adds one, the dashboard needs a token header, which isn't in this contract yet.
