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

### Database and migrations

The schema is managed by [Alembic](https://alembic.sqlalchemy.org) (`app/migrations/`). The app brings an empty or older database up to date every time it starts, so a fresh `uvicorn` just works. You can also run it yourself, which is what to do as a release step when several replicas share one Postgres:

```bash
alembic upgrade head                                  # apply every migration
alembic revision --autogenerate -m "what changed"     # after editing app/models.py; read the result before committing
alembic upgrade head --sql                            # print the SQL instead of running it
```

On Neon, use the pooled URL for `DATABASE_URL` and the direct one for `DATABASE_URL_DIRECT`. The app's connections are built for PgBouncer (no prepared statements, pre-ping, recycled every 5 minutes), and it never polls the database in the background, so Neon's compute can suspend when nobody is using it. Overdue stock holds are released when stock is read, when an order is placed and when orders are listed.

`tests/test_migrations.py` fails if a model changes without a migration. A database created before Alembic existed (tables but no `alembic_version`) is refused with a message: delete a development one, or run `alembic stamp head` if its schema is already current.

### Try Qwen3 without WhatsApp or Paystack

```bash
python -m app.chat_cli
```

A terminal chat with the same agent, tools and server rules as the bot. It checks that Ollama is running and has the model, shows each tool call in grey, and `/pay` stands in for Paystack's webhook. It is the quickest way to see how Qwen3 copes with Pidgin, haggling and odd requests.

## Configuration

Everything comes from environment variables or `.env`. See [`.env.example`](.env.example).

| Variable | Default | What it does |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./sowo.db` | SQLite in development, Postgres in production (`postgresql://user:pass@host:5432/sowo`; `postgres://` works too). On Neon, the pooled URL |
| `DATABASE_URL_DIRECT` | | Neon's unpooled URL, used only for migrations (PgBouncer isn't good for DDL). Empty means use `DATABASE_URL` |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | `http://localhost:11434`, `qwen3:8b` | Where Qwen3 runs and which model to use |
| `OLLAMA_TIMEOUT_SECONDS`, `OLLAMA_TEMPERATURE` | `120`, `0.3` | Model request timeout and sampling temperature |
| `AGENT_MAX_TOOL_ROUNDS` | `6` | Tool calls the model may chain in one reply |
| `WHATSAPP_VERIFY_TOKEN` | | A string you choose; Meta sends it back when you register the webhook |
| `WHATSAPP_APP_SECRET` | | Meta app secret, used to verify the signature on every delivery |
| `WHATSAPP_ACCESS_TOKEN` | | The platform's token for sending through the Cloud API. Each vendor's own number is stored on their row, see [Shop settings](#shop-settings) |
| `WHATSAPP_GRAPH_VERSION` | `v23.0` | Graph API version. Meta retires old ones, so check theirs |
| `WHATSAPP_ECHO_MODE` | `false` | Reply with `Echo: <text>` and skip the model, to test the webhook wiring |
| `MANUAL_PAYMENT_HOLD_MINUTES` | `180` | How long a bank-transfer order holds stock. Longer than `STOCK_HOLD_MINUTES` because transfers and checking a bank app take a while |
| `PAYSTACK_SECRET_KEY` | | Test or live secret key. Also verifies Paystack's webhook signature |
| `PAYSTACK_CALLBACK_URL` | | Where the buyer lands after paying (optional) |
| `PAYSTACK_CUSTOMER_EMAIL_DOMAIN` | `customers.sowo.invalid` | Paystack needs an email per payer; buyers get `<phone>@<this domain>` |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | This service's public address |
| `REPLY_DELAY_SECONDS` | `3` | A pause before each WhatsApp reply so it feels like typing |
| `STOCK_HOLD_MINUTES` | `15` | How long unpaid orders hold stock |
| `SIMULATOR_VENDOR_NAME` | `Ada's Footwear` | The demo shop the simulator's chats belong to |
| `SIMULATOR_ENABLED` | `true` | The `/simulator/*` endpoints behind the web app's demo page. Turn off when real buyers use the deployment |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated origins allowed to call the API |

## Accounts and sign-in

Vendors sign up with an email, a password and a business name. Passwords are hashed with Argon2id. A sign-in creates a session, and only a SHA-256 hash of its token is stored, so a copy of the database can't be replayed and a session can be revoked by deleting its row. Sessions last 30 days.

The API does not set cookies. The web app's server (a Next.js route handler) calls `/auth/login`, keeps the token in an httpOnly cookie on its own domain, and sends it to this API as `Authorization: Bearer <token>`. The browser never talks to the API directly.

Every dashboard route (`/conversations`, `/orders`, `/products`, `/orders/{id}/mark-paid` and the rest) needs that header and only shows the signed-in vendor's own data. Another vendor's conversation or order looks exactly like one that doesn't exist (404). The webhooks stay open because they carry their own signatures, and `/simulator/*` is controlled by `SIMULATOR_ENABLED`.

A vendor created before accounts existed, or by the demo seed, has no login. Give it one from the terminal (the password is asked for there):

```bash
python -m app.claim_vendor "Ada's Footwear" ada@example.com
```

## Shop settings

Everything that differs from one vendor to the next lives on the vendor's row in the database, not in the environment, so any number of vendors can share one deployment. The environment keeps only the platform's secrets (Meta app secret, access token, verify token; Paystack key; database; Ollama).

A signed-in vendor reads and changes their own with `GET` and `PATCH /vendor/settings` (send only what changes; `null` or an empty string clears an optional setting):

| Field | What it does |
| --- | --- |
| `whatsappPhoneNumberId` | The id Meta gives their WhatsApp business number. It is how a buyer's message finds the right vendor, and replies are sent from this number. Unique: two shops can't share one (`409`) |
| `alertPhone` | Their own phone, for "pack this" and "needs you" alerts (digits with country code; `+`, spaces and dashes are ignored) |
| `ownerName` | What buyers and the assistant call the person behind the shop ("Ada"). Falls back to the business name |
| `paymentMode` | `paystack` (a checkout link, confirmed by Paystack's webhook) or `manual` (the vendor's own bank account, see [Bank-transfer mode](#bank-transfer-mode)) |
| `bankName`, `bankAccountName`, `bankAccountNumber` | The account for `manual` mode. The number must be 10 digits. Choosing `manual` without a complete account is refused (`400`) |

A WhatsApp message to a number no vendor has connected is dropped (and logged); Sowo never guesses a vendor. Products, delivery zones, stock, offers and quotes are all per vendor too: the assistant for one shop cannot see, quote or sell another shop's products, and two shops may use the same sku.

Settings are not copied from the environment when upgrading. Variables from earlier versions (`WHATSAPP_PHONE_NUMBER_ID`, `VENDOR_ALERT_PHONE`, `PAYMENT_MODE`, `VENDOR_BANK_NAME`, `VENDOR_ACCOUNT_NAME`, `VENDOR_ACCOUNT_NUMBER`) are ignored: enter them through the settings endpoint once.

## Endpoints

The REST endpoints are specified in [`docs/api-contract.md`](../../docs/api-contract.md); the shared types are in `packages/shared`.

| Endpoint | For |
| --- | --- |
| `GET /conversations`, `GET /conversations/:id/messages` | Dashboard chats |
| `POST /conversations/:id/pause`, `.../resume`, `.../messages` | Ada pauses Sowo, resumes it, or replies herself (sent over WhatsApp) |
| `GET /orders`, `GET /products` | Dashboard orders and products (products include the floor price: vendor-only) |
| `POST /simulator/messages` | The `/try` page: a buyer message, answered by the same agent, without WhatsApp |
| `POST /simulator/payments` | The `/try` page: stands in for Paystack's webhook. Only touches simulator orders. Refused for bank-transfer orders |
| `POST /simulator/receipts` | The `/try` page in `manual` mode: the buyer says they've sent the transfer. Flags the order for Ada, pays nothing |
| `POST /auth/signup`, `POST /auth/login` | Create an account / sign in. Return `{ vendor, sessionToken, expiresAt }` |
| `POST /auth/logout`, `GET /auth/me` | End the current session / who am I |
| `POST /orders/{id}/mark-paid` | Ada confirms a bank-transfer order has reached her account. Refused for Paystack orders |
| `GET /webhooks/whatsapp` | Meta's one-off verification handshake |
| `POST /webhooks/whatsapp` | Buyer messages. Needs a valid `X-Hub-Signature-256` |
| `POST /webhooks/paystack` | Payment confirmations. Needs a valid `X-Paystack-Signature` |

Both webhooks answer `200` straight away and do the real work in the background, so Meta and Paystack never time out and retry.

## How a message is handled

1. The webhook checks the signature, drops anything seen before (`whatsapp_message_id` is unique), finds the vendor who owns the number the message was sent to, finds or creates the buyer's conversation with that vendor and saves the message.
2. Sowo only replies while the chat is **active**: not paused by the vendor, and not waiting for them after a hand-off. Otherwise the message is just saved for the dashboard.
3. The agent builds a prompt (the shop, delivery areas, and what the system already knows: agreed prices, the latest quote, any open order) plus the recent chat, and asks Qwen3.
4. Qwen3 answers with text or a **tool call**. Tools run on the server against the database; their results go back to the model, for up to `AGENT_MAX_TOOL_ROUNDS` rounds.
5. The final text is checked (below), saved with its tool calls for the dashboard, and sent over WhatsApp.

| Tool | The model passes | The server returns |
| --- | --- | --- |
| `search_catalog` | keywords | matching products with price and stock, never the floor |
| `evaluate_offer` | a sku and the buyer's offer in naira | `ACCEPT` / `COUNTER` / `REJECT` / `HANDOFF` and, if any, the price. Powered by `services/haggling.py` |
| `get_quote` | skus, quantities, a delivery area (no prices) | lines, delivery fee and total, priced from the database and the agreed offer |
| `request_payment` | a quote id | an order, held stock, and a Paystack payment link |
| `escalate_to_vendor` | a short reason | hands the chat to the vendor and alerts them |

## What the code enforces

- **The model never sees a floor price.** No tool returns one, the prompt doesn't name the concept, and `tests/test_agent.py` checks everything sent to the model for it.
- **Every amount in a reply must come from a tool.** `services/guard.py` finds each ₦ amount in the model's reply and compares it with what tools returned in this chat and what the buyer typed. A reply with an unbacked price is sent back to the model once to rewrite; if it still fails, the server writes a plain reply from the tool results.
- **The model can't announce a payment.** A reply claiming money arrived is blocked the same way. Receipts are written by the server, from the order, after Paystack's webhook.
- **Payment means a signed Paystack webhook.** `mark_order_paid` checks the reference and that the amount equals the order total in kobo. It is idempotent, so a retried webhook neither double-sells stock nor double-sends a receipt. A mismatched amount flags the chat and alerts the vendor instead.
- **Prices are re-derived, never trusted.** `request_payment` re-prices the quote just before creating the order, and fails if anything changed.

## Bank-transfer mode

A vendor who sets `paymentMode` to `manual` (with their account details) in their [shop settings](#shop-settings) stops using Paystack altogether. Ada is the example below:

1. After the haggle, `request_payment` creates the order, holds the stock for `MANUAL_PAYMENT_HOLD_MINUTES`, and gives the model Ada's bank, account name and number plus the order reference to use as the narration. If the account isn't set up (or isn't 10 digits), no order is created and the chat goes to Ada.
2. The buyer pays from their bank app and sends the receipt picture, or says "I don pay". A picture while an order is waiting flags it; words go to the model, which has a `report_payment_sent` tool that does the same. Either way Ada gets a WhatsApp alert once, and the hold is extended while she checks.
3. **Nothing is paid until Ada says so.** She looks in her own bank app, then taps **Mark paid** in the dashboard (`POST /orders/{id}/mark-paid`). That runs the same `mark_order_paid` as a Paystack webhook: stock is taken, the hold is released and the buyer gets a receipt written by the server. A second tap changes nothing and sends nothing.
4. If the hold expired before Ada looked, Mark paid revives the order when the stock is still there, and says so when it isn't.

The receipt is a prompt for Ada, not proof: the picture isn't downloaded, read or shown anywhere, because a screenshot is the easiest thing in the world to fake. The buyer can't mark their own order paid by any route, and the model can't announce a payment (the same guard blocks it as in Paystack mode).

## Connect WhatsApp

1. In [Meta for Developers](https://developers.facebook.com) create an app and add the **WhatsApp** product. Its API setup page gives you a test number's **phone number id** and an access token (the temporary one lasts 24 hours; use a System User token for anything longer).
2. Put the token in `.env` as `WHATSAPP_ACCESS_TOKEN`, along with the **app secret** (App settings → Basic) and a **verify token** you make up. Then give each vendor's **phone number id** to their shop with `PATCH /vendor/settings` (`whatsappPhoneNumberId`). One webhook serves every vendor; the number in each delivery decides whose it is.
3. Expose your local server over HTTPS (for example `ngrok http 8000` or `cloudflared tunnel --url http://localhost:8000`).
4. In the WhatsApp configuration, set the callback URL to `https://<your-tunnel>/webhooks/whatsapp` and the verify token to yours, then subscribe to the **messages** field.
5. Message your test number from your own phone. To check just the wiring first, set `WHATSAPP_ECHO_MODE=true`.

WhatsApp only lets a business send free-form text within 24 hours of the buyer's last message. Replies to buyers are always inside that window. A "pack this" alert to a vendor's `alertPhone` is not, unless Ada has messaged the number recently, so production needs an approved message template for alerts.

## Connect Paystack

1. Use your **test** secret key (Dashboard → Settings → API Keys & Webhooks) as `PAYSTACK_SECRET_KEY`.
2. Set the **test webhook URL** there to `https://<your-tunnel>/webhooks/paystack`.
3. Walk through a sale; Paystack's [test cards](https://paystack.com/docs/payments/test-payments/) complete a payment without moving money.

## Tests

```bash
pytest          # 259 tests
ruff check .
```

Tests never touch the network: Qwen3 is a scripted stand-in (`tests/helpers.py`), and Meta's Graph API and Paystack are recorded by `httpx.MockTransport`. They cover the full sale through the tools, the floor price never reaching the model, invented prices and fake "payment received" replies being caught, both signature checks, duplicate and out-of-order webhooks, paused and handed-off chats, outages of Meta, Paystack and Ollama, the simulator endpoints, and bank-transfer mode (account details, receipts, Mark paid, double taps, expired holds).

**Not yet verified:** a run against a live Qwen3, a live WhatsApp number and a live Paystack account. The agent and clients are written to those APIs' documented shapes and exercised end to end with stand-ins, but the first real run will probably need prompt tuning for the model you pick.

## Known limits

- One item type per order line, and one conversation per buyer per vendor.
- One Meta access token for the whole platform, which works for the vendors' numbers the platform's Meta app manages. Vendors don't bring their own tokens, so nothing secret per vendor is stored in the database.
- Paystack payments all go to the platform's Paystack account. Paying vendors out (subaccounts) isn't built.
- Qwen3 is not tuned for Nigerian Pidgin; the server, not the model, validates every offer and amount.
- Catalogue search is a keyword match, not semantic.
- Only text messages are read. A picture is treated as a receipt when a bank-transfer order is waiting; otherwise it gets a polite "text only" reply.
- Bank-transfer mode has no "payment not received" button yet: if the money never arrives Ada simply doesn't tap Mark paid and the hold lapses.
- Background work runs inside the web process, which is fine for one shop. A queue would be the next step at scale.
