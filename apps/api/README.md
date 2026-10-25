# apps/api

The Sowo backend. **Owned by the backend lead**; this folder is a placeholder until that work lands.

What goes here:

- WhatsApp Cloud API webhook (receive buyer messages, send replies)
- Qwen3 via Ollama with tool calling (`search_catalog`, `evaluate_offer`, `get_quote`, `request_payment`)
- Floor-price engine: the server, not the model, decides every price, total and stock change
- Postgres for products, conversations, messages and orders
- Paystack (test mode) payment links and webhook verification

The HTTP API the web app expects is specified in [`docs/api-contract.md`](../../docs/api-contract.md), and the TypeScript types live in [`packages/shared/src/api.ts`](../../packages/shared/src/api.ts). Until this service exists, `apps/web` serves a mock of the same contract at `/api/mock`.
