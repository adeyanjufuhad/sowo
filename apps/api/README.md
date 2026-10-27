# apps/api

Sowo's backend: FastAPI and SQLAlchemy. **Qwen3 reads each WhatsApp message and picks a tool; our code decides every price, total, stock change and payment.**

```
WhatsApp buyer ─▶ POST /webhooks/whatsapp ─▶ agent ──▶ Qwen3 (Ollama or a hosted API) picks a tool
                                               │              │
                                               ▼              ▼
                                   server rules: price engine, quotes, stock holds
                                               │
                  Paystack ◀── payment link ◀──┘      Paystack ─▶ POST /webhooks/paystack ─▶ order PAID,
                                                                                receipt to buyer, "pack this" to Ada
```

## Run it

Needs Python 3.11+ and Qwen3 from one of two places: [Ollama](https://ollama.com) on your machine (below), or a hosted OpenAI-compatible API, which needs no GPU (see [Qwen3 on a hosted API](#qwen3-on-a-hosted-api)).

```bash
ollama pull qwen3:8b

cd apps/api
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e . --group dev
cp .env.example .env                                  # then fill in your own values (never commit it)
# For a demo on your own machine, also put these two lines in .env (see "Demo mode" below):
#   ENVIRONMENT=development
#   SIMULATOR_ENABLED=true

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

### Demo mode

Nothing demo-related is on by default. A fresh deployment has no shop, no products and no `/simulator/*` endpoints; vendors sign up and add their own catalog. To run the demo on your own machine, set `ENVIRONMENT=development` (allows the seed commands) and `SIMULATOR_ENABLED=true` (the web app's `/try` page) in your local `.env`. `python -m app.seed`, `python -m app.seed_demo` and `python -m app.chat_cli` all refuse to run unless `ENVIRONMENT=development`, so they can't fill a real database by accident. If a production deployment starts with the simulator on, it logs a warning.

### Qwen3 on a hosted API

To keep the model off your own machine, point the app at any OpenAI-compatible `/chat/completions` endpoint that serves an open-weight Qwen3 model and supports tool calling (Groq, OpenRouter, Cloudflare Workers AI, a vLLM server of your own). In `.env`:

```bash
MODEL_PROVIDER=openai
LLM_BASE_URL=https://api.groq.com/openai/v1     # example: Groq
LLM_API_KEY=...                                  # from the host's console; never commit it
LLM_MODEL=qwen/qwen3.8-27b                       # the host's id for a Qwen3 model; check its current list
LLM_REASONING_EFFORT=none                        # optional: asks hosts that support it not to "think" first
```

Startup fails with a clear message if `MODEL_PROVIDER=openai` is set without `LLM_BASE_URL` and `LLM_MODEL`. The app sends one request per model turn and retries once, after at most five seconds, if the host answers 429 or 503. Free tiers cap requests and tokens per minute and per day, so they suit a demo and not real traffic, and some log prompts, which contain buyers' messages. Confirm the model is open-weight Qwen3 and that the host supports its tool calls before relying on it.

### Try Qwen3 without WhatsApp or Paystack

```bash
python -m app.chat_cli                                # needs ENVIRONMENT=development
```

A terminal chat with the same agent, tools and server rules as the bot. With Ollama it checks that the server is running and has the model (with a hosted API it just starts), shows each tool call in grey, and `/pay` stands in for Paystack's webhook. It is the quickest way to see how Qwen3 copes with Pidgin, haggling and odd requests.

## Configuration

Everything comes from environment variables or `.env`. See [`.env.example`](.env.example).

| Variable | Default | What it does |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///./sowo.db` | SQLite in development, Postgres in production (`postgresql://user:pass@host:5432/sowo`; `postgres://` works too). On Neon, the pooled URL |
| `DATABASE_URL_DIRECT` | | Neon's unpooled URL, used only for migrations (PgBouncer isn't good for DDL). Empty means use `DATABASE_URL` |
| `MODEL_PROVIDER` | `ollama` | `ollama` for a local Ollama, `openai` for a hosted OpenAI-compatible API |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | `http://localhost:11434`, `qwen3:8b` | Where a local Qwen3 runs and which model to use |
| `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | _(empty)_ | The hosted endpoint, its key and the Qwen3 model id. Needed when `MODEL_PROVIDER=openai` |
| `LLM_REASONING_EFFORT` | _(empty)_ | Sent as `reasoning_effort` when set (Groq takes `none` for Qwen3). Empty sends nothing |
| `OLLAMA_TIMEOUT_SECONDS`, `OLLAMA_TEMPERATURE` | `120`, `0.3` | Model request timeout and sampling temperature (used by both providers) |
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
| `ENVIRONMENT` | `production` | `development` allows the demo commands (`app.seed`, `app.seed_demo`, `app.chat_cli`). Leave it unset on a real deployment |
| `SIMULATOR_ENABLED` | `false` | The `/simulator/*` endpoints behind the web app's `/try` demo page. They have no sign-in, so keep them off where real buyers are |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated origins allowed to call the API |
| `LOG_FORMAT`, `LOG_LEVEL` | `json`, `INFO` | `json` is one object per line for a log host, `text` reads better in a terminal |
| `RATE_LIMIT_ENABLED` | `true` | Switch for every rate limit below |
| `RATE_LIMIT_AUTH_PER_MINUTE` | `20` | Sign-ups plus sign-in attempts per client address per minute |
| `RATE_LIMIT_WEBHOOKS_PER_MINUTE` | `600` | WhatsApp and Paystack webhook calls per client address per minute |
| `LOGIN_MAX_FAILURES` | `10` | Wrong passwords allowed per email address in 15 minutes. A right password clears the count |
| `CLIENT_IP_HEADER` | _(empty)_ | Header holding the real client address, such as `x-forwarded-for`. Set it only when the API can be reached through a trusted proxy alone, otherwise callers can spoof it |

## Running it in production

## Running it in production

- **Health and readiness.** `GET /health` says the process is up and never touches the database, so a liveness probe can't keep Neon's compute awake. `GET /ready` runs `SELECT 1` and answers `503 {"status":"unavailable"}` when the database can't be reached (the log line names the error class only, never the connection string). Point the host's *readiness* check at `/ready` and its *liveness* check at `/health`; a readiness probe every few seconds keeps a serverless database awake, so use a long interval, or none.
- **Logs.** One line per request: method, the route pattern (`/conversations/{conversation_id}/messages`, never the real URL, so ids, phone numbers and query strings stay out), status and milliseconds, with a `request_id`. Send `X-Request-ID` to choose it (letters, digits, `.`, `_`, `-`, up to 64 characters); otherwise one is made up. It is returned in the `X-Request-ID` response header and attached to every log line written while handling the request. Anything that looks like a phone number (seven or more digits) is cut to `***` plus its last three digits, and bearer tokens and Paystack secret keys are masked. Uvicorn's own access log is turned off because it prints query strings, which carry the WhatsApp verify token. Successful `/health` and `/ready` calls aren't logged.
- **Rate limits.** Sign-up and sign-in share an allowance per client address, the webhooks share another (checked before the signature, so an unsigned flood is cheap to refuse), and failed sign-ins are also counted per email so a guesser can't spread attempts over addresses. Refusals are `429 { "error": { "code": "RATE_LIMITED" } }` with a `Retry-After` header. The counters are in each process's memory: with several replicas each enforces its own limit, and they reset on restart. Use the host's edge limits if you need a shared one. The web app forwards the visitor's address as `x-forwarded-for`; without `CLIENT_IP_HEADER` the API sees every sign-in coming from the web server, so the per-address limit would be shared by all visitors.
- **Unexpected errors** are logged with a traceback and answered `500` with a generic message.

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

## Catalog

A vendor builds their own catalog with `POST /products`, `PATCH /products/:id` and `DELETE /products/:id`, and the areas they deliver to with `/delivery-zones`. Everything is scoped to the signed-in vendor, and another vendor's id is a `404`.

- Money is whole kobo and the **floor price** (`floorPriceKobo`) must be more than zero and no more than the price. It is the lowest price the vendor will accept, shown only to them here: it never reaches the model (search results and every tool answer leave it out, and tests check everything sent to the model for it).
- A `sku` is 1 to 64 letters, numbers, dots, dashes or underscores, stored upper-case, and unique within one vendor's catalog (two shops may use the same one).
- Changing a price, stock or delivery fee applies from the very next message: the assistant reads the database on every turn, and `request_payment` re-prices a quote just before creating the order, so a buyer is never charged a stale price.
- `DELETE /products/:id` removes a product nobody has touched. One that has been ordered, haggled over or held is **archived** instead (`{ "deleted": false, "archived": true }`): it disappears from the dashboard, the assistant and new quotes, but the orders and chats that mention it keep working. An archived product's sku stays reserved.
- Delivery zones can always be deleted: an order keeps the area name it was placed with. An area is unique per vendor, ignoring case.

## Endpoints

The REST endpoints are specified in [`docs/api-contract.md`](../../docs/api-contract.md); the shared types are in `packages/shared`.

| Endpoint | For |
| --- | --- |
| `GET /conversations`, `GET /conversations/:id/messages` | Dashboard chats |
| `POST /conversations/:id/pause`, `.../resume`, `.../messages` | Ada pauses Sowo, resumes it, or replies herself (sent over WhatsApp) |
| `GET /orders`, `GET /products` | Dashboard orders and products (products include the floor price: vendor-only) |
| `POST /products`, `PATCH /products/:id`, `DELETE /products/:id` | The vendor's catalog. See [Catalog](#catalog) |
| `GET /delivery-zones`, `POST /delivery-zones`, `PATCH`/`DELETE /delivery-zones/:id` | Where the vendor delivers, and the fee for each area |
| `GET /vendor/settings`, `PATCH /vendor/settings` | The vendor's WhatsApp number, alert phone, owner name and payment setup. See [Shop settings](#shop-settings) |
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
- Paystack payments all go to the platform's Paystack account. Paying vendors out (subaccounts or transfers) is out of scope by decision; vendors who want the money in their own account use bank-transfer mode.
- Qwen3 is not tuned for Nigerian Pidgin; the server, not the model, validates every offer and amount.
- Catalogue search is a keyword match, not semantic.
- Only text messages are read. A picture is treated as a receipt when a bank-transfer order is waiting; otherwise it gets a polite "text only" reply.
- Bank-transfer mode has no "payment not received" button yet: if the money never arrives Ada simply doesn't tap Mark paid and the hold lapses.
- Background work runs inside the web process, which is fine for one shop. A queue would be the next step at scale.
