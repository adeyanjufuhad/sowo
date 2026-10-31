# Contract notes

## Stage 1 conversation persistence states

Stage 1 persists the explicitly requested `ACTIVE`, `NEEDS_ATTENTION`, and `PAUSED` states. The HTTP contract uses `AI_ACTIVE`, `NEEDS_ATTENTION`, `HUMAN_TAKEOVER`, and `CLOSED`. Before dashboard endpoints are added, define the API mapping (expected: `ACTIVE` to `AI_ACTIVE`, `PAUSED` to `HUMAN_TAKEOVER`) or migrate the stored enum.

Stage 4 keeps the requested storage transitions (`PAUSED` plus `ai_paused`, then `ACTIVE`) and serializes them to the API contract's `HUMAN_TAKEOVER` and `AI_ACTIVE` statuses. `NEEDS_ATTENTION` maps directly. The storage enum has no `CLOSED` value yet.

## Stage 4 tool-call shape

The Stage 4 wording calls the tool-call field `name`, while the shared TypeScript contract defines it as `tool`. Dashboard responses follow the shared contract: `tool`, `input`, and `output`.

## Stage 5: the agent, WhatsApp, Paystack and the simulator

`POST /simulator/messages` and `POST /simulator/payments` are implemented as in the contract, plus a `SIMULATOR_ENABLED` switch (default **off**; turn it on for a local demo) so a deployment that serves real buyers never exposes them. `/simulator/payments` only ever touches orders of simulator conversations, never a real buyer's.

Where the real backend differs from, or adds to, `docs/api-contract.md` (for its owner to fold in):

- **`evaluate_offer` decisions.** The haggling engine returns `ACCEPT`, `COUNTER`, `REJECT` (offer under half the list price) and `HANDOFF` (repeated offers below the floor), not `HOLD`. `REJECT` and `HANDOFF` carry no price. The shared type `OfferDecision` now includes both.
- **`sku` in tool inputs.** `evaluate_offer` and `get_quote` inputs also carry an optional `sku` (the readable form of `productId`), so the dashboard can show `LOAF-BLK-43` instead of a UUID. `search_catalog` hits include `sku`, as the contract already says.
- **`escalate_to_vendor` is not traced.** The model has a fifth tool for hand-offs, but it is not written to `toolCalls`, because the contract and the web app only know four tools. A hand-off shows as the conversation's `NEEDS_ATTENTION` status. `HANDOFF` from `evaluate_offer` is traced as normal.
- **Ids.** Orders, conversations, messages and products have UUID ids (the web mock used `ord_1043` style ids). `quoteId` is `q_` plus eight hex characters. The readable order handle is `paymentReference` (`SW-…`), and the dashboard should show that rather than `id`.
- **`paymentUrl`.** For WhatsApp buyers it is Paystack's `authorization_url`. For simulator chats it is the placeholder `https://paystack.test/pay/<reference>`. If Paystack is not configured or is down, no order is left behind: `request_payment` fails, the held stock is released and the chat goes to the vendor.
- **Order status.** Orders store `PENDING`, `PAID`, `EXPIRED` and `CANCELLED`. The API shows `PAID` as `PAID`, `EXPIRED` and `CANCELLED` as `FAILED`, and the rest as `PENDING`. `REFUNDED` is never produced.
- **Fulfilment.** Paid orders report `PACKAGING`. There is no way yet to move an order to `SHIPPED` or `DELIVERED`.
- **Conversation `CLOSED`** is still never produced.

### Accounts and sign-in

- **Every dashboard endpoint now needs `Authorization: Bearer <sessionToken>`** and returns only the signed-in vendor's data: `GET /conversations`, `GET /conversations/:id/messages`, `POST /conversations/:id/pause`, `.../resume`, `.../messages`, `GET /orders`, `GET /products`, `POST /orders/:id/mark-paid`. Another vendor's id is a `404`. Without a valid token the response is `401` with `{ "error": { "code": "UNAUTHORIZED", "message": "Sign in to continue" } }` and a `WWW-Authenticate: Bearer` header. `ApiError.error.code` gains `"UNAUTHORIZED"`.
- **New:** `POST /auth/signup` `{ email, password, businessName }` (`201`, `400` with a readable message, `409` for a taken email or business name), `POST /auth/login` `{ email, password }` (`401` "Incorrect email or password" for both a wrong password and an unknown email), `POST /auth/logout` (revokes the token used), `GET /auth/me`. The sign-up and login responses are `{ vendor: { id, name, email }, sessionToken, expiresAt }`. The token is shown once; the API stores only its hash.
- **Not authenticated:** `/health`, `/ready`, `/webhooks/*` (signatures) and `/simulator/*` (gated by `SIMULATOR_ENABLED`). Simulator chats belong to the demo shop (`SIMULATOR_VENDOR_NAME`).
- **Tables and columns.** `vendors.email`, `vendors.password_hash` and `vendors.created_at`; new `vendor_sessions`; `conversations.vendor_id` (not null, existing rows go to the first vendor by name). Migration `0002`.

### Shop settings and several vendors

- **New:** `GET /vendor/settings` and `PATCH /vendor/settings` (signed in; partial update; `400` with a readable message, `409` when the WhatsApp number belongs to another shop). Shape: `{ businessName, ownerName, whatsappPhoneNumberId, alertPhone, paymentMode: "paystack" | "manual", bankName, bankAccountName, bankAccountNumber, paymentReady, whatsappConnected }`. The shared types are `VendorSettings` and `VendorSettingsUpdate`.
- **Moved out of the environment:** `WHATSAPP_PHONE_NUMBER_ID`, `VENDOR_ALERT_PHONE`, `PAYMENT_MODE` and `VENDOR_BANK_NAME` / `VENDOR_ACCOUNT_NAME` / `VENDOR_ACCOUNT_NUMBER` are gone. They are columns on `vendors` and are not copied over on upgrade.
- **Routing.** A WhatsApp delivery is matched to a vendor by `value.metadata.phone_number_id`. Unknown numbers are dropped (still `200`, so Meta doesn't retry). Replies and alerts are sent from the vendor's own number.
- **Scoping.** `search_catalog`, sku lookup, delivery zones, quotes and orders only see the conversation's vendor. A sku is unique per vendor, not globally.
- **Columns.** `vendors.owner_name`, `whatsapp_phone_number_id` (unique), `alert_phone`, `payment_mode` (`paystack` by default), `bank_name`, `bank_account_name`, `bank_account_number`; `products` is unique on `(vendor_id, sku)`. Migration `0003`.
- **Wording.** The buyer-facing receipt names the owner (`ownerName`, else the business name) instead of "Ada"; the "I've sent your receipt" reply says "the owner".

### Catalog management

- **New (signed in, scoped to the vendor):** `POST /products` (`201 { product }`), `PATCH /products/:id` (`200 { product }`), `DELETE /products/:id` (`200 { deleted, archived }`), `GET /delivery-zones` (`{ zones }`), `POST /delivery-zones` (`201 { zone }`), `PATCH /delivery-zones/:id` (`200 { zone }`), `DELETE /delivery-zones/:id` (`204`). `400` with a readable message for invalid values, `409` for a duplicate sku or area, `404` for anything that isn't the vendor's.
- **`Product`** (also what `GET /products` returns) gains optional `description`, `size` and `colour`. `POST` takes `{ sku, name, description?, size?, colour?, basePriceKobo, floorPriceKobo, stockOnHand?, imageUrl? }`; `PATCH` takes any of them (`size` and `colour` accept `null`). Money must be whole kobo (a float or a string is a `400`), and `0 < floorPriceKobo <= basePriceKobo`.
- **Archiving.** Deleting a product that appears in an order, offer or stock hold archives it (`products.archived_at`, migration `0004`): it is gone from `GET /products`, the assistant and quotes, and its sku stays taken.

### Bank-transfer mode (a vendor's `paymentMode: "manual"`)

- **`Order.paymentMethod`** (`"PAYSTACK" | "MANUAL"`) and **`Order.receiptReportedAt`** (ISO string, bank transfers only) are new optional fields. The shared `Order` type has both.
- **`request_payment` output** in manual mode has no `paymentUrl`; it has `method: "MANUAL"` and `bank: { bankName, accountName, accountNumber }`. The shared type makes `paymentUrl` optional and adds `method` and `bank`.
- **`POST /orders/{id}/mark-paid`** (new, no body). `200 { order, message? }` where `message` is the buyer's receipt and is absent on a repeat tap. `404` unknown order, `409` for a Paystack order, a cancelled order, or an expired one whose stock is gone.
- **`POST /simulator/receipts`** (new) takes `{ reference }` and returns `{ order, messages }`. `404` unless it is a simulator order, `409` unless it is a pending bank-transfer order. `POST /simulator/payments` now `409`s for bank-transfer orders.
- **`report_payment_sent`** is a sixth model tool, offered only in manual mode, and like `escalate_to_vendor` it is not written to `toolCalls`.
- **Columns.** `orders.payment_method` and `orders.receipt_reported_at` (migration `0001`).

New tables: `quotes` (a priced basket the model was shown; `request_payment` turns one into an order). Existing databases get it from `create_all` on startup.

### Production hardening

- **`GET /ready`** (new) answers `200 { "status": "ready" }` when the database responds and `503 { "status": "unavailable" }` otherwise. `GET /health` is unchanged and never touches the database.
- **`429`** with `{ "error": { "code": "RATE_LIMITED", "message": ... } }` and a `Retry-After` header (seconds) can come from `POST /auth/signup`, `POST /auth/login` and `/webhooks/*`. `ApiError.error.code` gains `"RATE_LIMITED"`. After too many wrong passwords for one email, `POST /auth/login` is `429` even for the right password until the 15-minute window passes.
- **Every response carries `X-Request-ID`.** Send your own to correlate logs.
- **Unexpected errors** are `500` with `{ "error": { "code": "INTERNAL", "message": "Something went wrong on our side" } }`.

### Product pictures and categories

- **New:** `POST /product-images` (signed in) takes `{ data }`, a base64 JPEG, PNG, WebP or GIF of at most 1.5 MB, and returns `201 { imageUrl }`, which looks like `/product-images/<id>`. Put it in a product's `imageUrl` to use it. The type is read from the bytes, not trusted from the upload, and SVG is refused. `400` for anything else, or once a vendor holds 200 pictures. The web app shrinks photos to 1000 px JPEG before sending. Shared types `ProductImageUpload` and `ProductImageUploadResponse`; endpoint `uploadProductImage`.
- **New:** `GET /product-images/{id}` (no sign-in, so buyers' browsers can show it; ids are random UUIDs) returns the picture with `Cache-Control: public, max-age=31536000, immutable` and `X-Content-Type-Options: nosniff`. `404` if unknown. The web app loads it through `/api/proxy/product-images/<id>`, which now passes bytes through untouched.
- **`imageUrl`** on `POST`/`PATCH /products` accepts an uploaded picture of the vendor's own (another vendor's is a `400`) or, as before, an `http(s)://` address. A picture no product uses any more is deleted when its product changes picture or is deleted.
- **`Product.category`** (string or `null`, at most 64 characters) is new on `GET /products` and accepted by `POST`/`PATCH /products` (`null` clears it). The assistant's `search_catalog` searches it (so "shoes" finds the vendor's "Shoes" category, and a trailing "s" is forgiven) and returns it per result; the system prompt lists the vendor's categories.
- **Columns.** New table `product_images` (migration `0005`); `products.category` (migration `0006`).

### Shop name

- **`PATCH /vendor/settings`** accepts `businessName` (at most 120 characters, spaces collapsed). Blank or `null` is a `400`; another shop's name is a `409`. `GET /vendor/settings` and `GET /auth/me` return the new name. Shared type: `VendorSettingsUpdate.businessName`.
- **New:** `GET /simulator/shop` (no sign-in; `404` when the simulator is off, `409` if the demo shop doesn't exist) returns `{ businessName, ownerName }`, where `ownerName` falls back to the business name as the assistant's does. The /try page shows these instead of a fixed "Ada's Footwear". Shared type `SimulatorShop`; endpoint `getSimulatorShop`.
- **The demo shop is remembered.** `SIMULATOR_VENDOR_NAME` finds the shop by name the first time and stores that setting on it (`vendors.simulator_key`, unique, migration `0007`). After that the shop can rename itself and /try keeps talking to it, and a new shop signing up with the old name doesn't take the demo over. Changing `SIMULATOR_VENDOR_NAME` to another existing shop's name moves the demo there.
