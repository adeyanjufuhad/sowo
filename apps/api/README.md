# apps/api

Sowo's backend: FastAPI and SQLAlchemy. **Qwen3 reads each WhatsApp message and picks a tool; our code decides every price, total, stock change and payment.**

```
WhatsApp buyer ─▶ POST /webhooks/whatsapp ─▶ agent ──▶ Qwen3 (Ollama) picks a tool
                                               │              │
                                               ▼              ▼
                                   server rules: price engine, quotes, stock holds
                                               │
                  Paystack ◀── payment link ◀──┘      Paystack ─▶ POST /webhooks/paystack ─▶ order PAID,
                                                                                receipt to buyer, "pack this" to Ada
```

## Run it

Needs Python 3.11+ and [Ollama](https://ollama.com).

```bash
ollama pull qwen3:8b

cd apps/api
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e . --group dev
cp .env.example .env                                  # then fill in your own values (never commit it)

python -m app.seed_demo                               # Ada's Footwear: products, delivery zones, a few chats
uvicorn app.main:app --reload                         # http://localhost:8000/health
```

Then point the web app at it: set `NEXT_PUBLIC_API_URL=http://localhost:8000` in `apps/web/.env.local`.

### Try Qwen3 without WhatsApp or Paystack

```bash
python -m app.chat_cli
```

A terminal chat with the same agent, tools and server rules as the bot. It checks that Ollama is running and has the model, shows each tool call in grey, and `/pay` stands in for Paystack's webhook. It is the quickest way to see how Qwen3 copes with Pidgin, haggling and odd requests.

## Configuration

Everything comes from environment variables or `.env`. See [`.env.example`](.env.example).

| Variable | Default | What it does |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./sowo.db` | SQLAlchemy URL. SQLite in development. |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | `http://localhost:11434`, `qwen3:8b` | Where Qwen3 runs and which model to use |
| `OLLAMA_TIMEOUT_SECONDS`, `OLLAMA_TEMPERATURE` | `120`, `0.3` | Model request timeout and sampling temperature |
| `AGENT_MAX_TOOL_ROUNDS` | `6` | Tool calls the model may chain in one reply |
| `WHATSAPP_VERIFY_TOKEN` | | A string you choose; Meta sends it back when you register the webhook |
| `WHATSAPP_APP_SECRET` | | Meta app secret, used to verify the signature on every delivery |
| `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID` | | Used to send replies through the Cloud API |
| `WHATSAPP_GRAPH_VERSION` | `v23.0` | Graph API version. Meta retires old ones, so check theirs |
| `WHATSAPP_ECHO_MODE` | `false` | Reply with `Echo: <text>` and skip the model, to test the webhook wiring |
| `VENDOR_ALERT_PHONE` | | Ada's own WhatsApp number (digits, with country code) for "pack this" and "needs you" alerts |
| `PAYSTACK_SECRET_KEY` | | Test or live secret key. Also verifies Paystack's webhook signature |
| `PAYSTACK_CALLBACK_URL` | | Where the buyer lands after paying (optional) |
| `PAYSTACK_CUSTOMER_EMAIL_DOMAIN` | `customers.sowo.invalid` | Paystack needs an email per payer; buyers get `<phone>@<this domain>` |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | This service's public address |
| `REPLY_DELAY_SECONDS` | `3` | A pause before each WhatsApp reply so it feels like typing |
| `STOCK_HOLD_MINUTES` | `15` | How long unpaid orders hold stock |
| `SIMULATOR_ENABLED` | `true` | The `/simulator/*` endpoints behind the web app's demo page. Turn off when real buyers use the deployment |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated origins allowed to call the API |

## Endpoints

The REST endpoints are specified in [`docs/api-contract.md`](../../docs/api-contract.md); the shared types are in `packages/shared`.

| Endpoint | For |
| --- | --- |
| `GET /conversations`, `GET /conversations/:id/messages` | Dashboard chats |
| `POST /conversations/:id/pause`, `.../resume`, `.../messages` | Ada pauses Sowo, resumes it, or replies herself (sent over WhatsApp) |
| `GET /orders`, `GET /products` | Dashboard orders and products (products include the floor price: vendor-only) |
| `POST /simulator/messages` | The `/try` page: a buyer message, answered by the same agent, without WhatsApp |
| `POST /simulator/payments` | The `/try` page: stands in for Paystack's webhook. Only touches simulator orders |
| `GET /webhooks/whatsapp` | Meta's one-off verification handshake |
| `POST /webhooks/whatsapp` | Buyer messages. Needs a valid `X-Hub-Signature-256` |
| `POST /webhooks/paystack` | Payment confirmations. Needs a valid `X-Paystack-Signature` |

Both webhooks answer `200` straight away and do the real work in the background, so Meta and Paystack never time out and retry.

## How a message is handled

1. The webhook checks the signature, drops anything seen before (`whatsapp_message_id` is unique), finds or creates the buyer's conversation and saves the message.
2. Sowo only replies while the chat is **active**: not paused by Ada, and not waiting for her after a hand-off. Otherwise the message is just saved for the dashboard.
3. The agent builds a prompt (the shop, delivery areas, and what the system already knows: agreed prices, the latest quote, any open order) plus the recent chat, and asks Qwen3.
4. Qwen3 answers with text or a **tool call**. Tools run on the server against the database; their results go back to the model, for up to `AGENT_MAX_TOOL_ROUNDS` rounds.
5. The final text is checked (below), saved with its tool calls for the dashboard, and sent over WhatsApp.

| Tool | The model passes | The server returns |
| --- | --- | --- |
| `search_catalog` | keywords | matching products with price and stock, never the floor |
| `evaluate_offer` | a sku and the buyer's offer in naira | `ACCEPT` / `COUNTER` / `REJECT` / `HANDOFF` and, if any, the price. Powered by `services/haggling.py` |
| `get_quote` | skus, quantities, a delivery area (no prices) | lines, delivery fee and total, priced from the database and the agreed offer |
| `request_payment` | a quote id | an order, held stock, and a Paystack payment link |
| `escalate_to_vendor` | a short reason | hands the chat to Ada and alerts her |

## What the code enforces

- **The model never sees a floor price.** No tool returns one, the prompt doesn't name the concept, and `tests/test_agent.py` checks everything sent to the model for it.
- **Every amount in a reply must come from a tool.** `services/guard.py` finds each ₦ amount in the model's reply and compares it with what tools returned in this chat and what the buyer typed. A reply with an unbacked price is sent back to the model once to rewrite; if it still fails, the server writes a plain reply from the tool results.
- **The model can't announce a payment.** A reply claiming money arrived is blocked the same way. Receipts are written by the server, from the order, after Paystack's webhook.
- **Payment means a signed Paystack webhook.** `mark_order_paid` checks the reference and that the amount equals the order total in kobo. It is idempotent, so a retried webhook neither double-sells stock nor double-sends a receipt. A mismatched amount flags the chat and alerts Ada instead.
- **Prices are re-derived, never trusted.** `request_payment` re-prices the quote just before creating the order, and fails if anything changed.

## Connect WhatsApp

1. In [Meta for Developers](https://developers.facebook.com) create an app and add the **WhatsApp** product. Its API setup page gives you a test number's **phone number id** and an access token (the temporary one lasts 24 hours; use a System User token for anything longer).
2. Put the phone number id and token in `.env`, along with the **app secret** (App settings → Basic) and a **verify token** you make up.
3. Expose your local server over HTTPS (for example `ngrok http 8000` or `cloudflared tunnel --url http://localhost:8000`).
4. In the WhatsApp configuration, set the callback URL to `https://<your-tunnel>/webhooks/whatsapp` and the verify token to yours, then subscribe to the **messages** field.
5. Message your test number from your own phone. To check just the wiring first, set `WHATSAPP_ECHO_MODE=true`.

WhatsApp only lets a business send free-form text within 24 hours of the buyer's last message. Replies to buyers are always inside that window. A "pack this" alert to `VENDOR_ALERT_PHONE` is not, unless Ada has messaged the number recently, so production needs an approved message template for alerts.

## Connect Paystack

1. Use your **test** secret key (Dashboard → Settings → API Keys & Webhooks) as `PAYSTACK_SECRET_KEY`.
2. Set the **test webhook URL** there to `https://<your-tunnel>/webhooks/paystack`.
3. Walk through a sale; Paystack's [test cards](https://paystack.com/docs/payments/test-payments/) complete a payment without moving money.

## Tests

```bash
pytest          # 141 tests
ruff check .
```

Tests never touch the network: Qwen3 is a scripted stand-in (`tests/helpers.py`), and Meta's Graph API and Paystack are recorded by `httpx.MockTransport`. They cover the full sale through the tools, the floor price never reaching the model, invented prices and fake "payment received" replies being caught, both signature checks, duplicate and out-of-order webhooks, paused and handed-off chats, outages of Meta, Paystack and Ollama, and the simulator endpoints.

**Not yet verified:** a run against a live Qwen3, a live WhatsApp number and a live Paystack account. The agent and clients are written to those APIs' documented shapes and exercised end to end with stand-ins, but the first real run will probably need prompt tuning for the model you pick.

## Known limits

- One vendor, one item type per order line, and one conversation per buyer phone number.
- Qwen3 is not tuned for Nigerian Pidgin; the server, not the model, validates every offer and amount.
- Catalogue search is a keyword match, not semantic.
- Only text messages are read. Pictures get a polite "text only" reply.
- Background work runs inside the web process, which is fine for one shop. A queue would be the next step at scale.
