# Sowo: handoff for another AI agent

Written 2026-10-27. Deadline: **OSCA Ile-Ife OPEN//BUILD 2026, Thursday 29 Oct 2026, 11:59 PM WAT.**
Repo: https://github.com/adeyanjufuhad/sowo (public, MIT). Owner: Fuhad Adeyanju.

Read this whole file, then `apps/api/AGENTS.md`, `apps/api/README.md` and `apps/api/CONTRACT_NOTES.md`.

## What Sowo is

An AI sales assistant for Nigerian WhatsApp vendors. A buyer messages a vendor's WhatsApp number; Qwen3 understands them and replies; the vendor sees chats and orders in a web dashboard.

## Rules that must not be broken

1. **The model only understands the buyer and writes the reply.** The server decides every price, total, stock change and payment. The model picks tools; the tools compute.
2. **The model must never see `floor_price`** (the vendor's lowest acceptable price). Not in prompts, tool output, logs shown to the model, or hints.
3. **Money is integer kobo everywhere.**
4. **Open-weight Qwen3 only.** No other model in the product.
5. **No secrets or real phone numbers committed.** Secrets live in gitignored `apps/api/.env`. Never paste Neon connection strings or API keys into commits, logs, tests, issues or chat.
6. **Never edit `docs/api-contract.md`.** Contract changes go in `apps/api/CONTRACT_NOTES.md`.
7. Money and haggling logic needs unit tests. `pytest` and `ruff check` must pass.
8. **Do not run migrations or seed data against Neon `main`** (branch `br-autumn-bonus-za1zx0do`, project "sowo", id `super-dew-44418945`, aws-eu-west-2). It is empty and waits on Fuhad's go-ahead. The dev branch is `br-little-sky-zay65g8i`.
9. Don't push to `main` or merge PRs without Fuhad's say-so. Don't build Dockerfile / docker-compose / DOCKER.md: another engineer owns them (brief: `docs/tasks/backend-docker-stack.md`, untracked in Fuhad's main checkout).

## Layout

pnpm monorepo.
- `apps/api`: FastAPI + SQLAlchemy 2 + Alembic + psycopg3 + argon2-cffi + pydantic-settings. Python 3.11+. SQLite for tests, Postgres (Neon) for real use.
- `apps/web`: Next.js 16 (App Router; `proxy.ts` replaces middleware), React 19, Tailwind v4, Vitest.
- `packages/shared`: TypeScript types for the API (`src/api.ts`).

## State of the code (all on `main` unless noted)

Done and merged (PR #3 and PR #4):
- Qwen3 agent with tool calling, WhatsApp webhook (signature checked), Paystack webhook, bank-transfer payment mode, simulator endpoints for the `/try` demo page.
- Postgres + Alembic (migrations 0001-0004), Neon-friendly pooling, no background polling (so Neon compute can suspend).
- Vendor accounts (Argon2id, hashed session tokens), dashboard scoped per vendor, web sign-in via a Next.js proxy with an httpOnly cookie `sowo_session`.
- Several vendors on one deployment: WhatsApp number, alert phone, owner name, payment mode and bank details are columns on the vendor row; inbound messages route by `phone_number_id`; unknown numbers are dropped.
- Catalog management: product and delivery-zone CRUD; products that orders refer to are archived, not deleted. Web pages `/dashboard/settings` and `/dashboard/catalog`.
- Demo off by default: `ENVIRONMENT` defaults to `production`, `SIMULATOR_ENABLED` to `false`; `app.seed`, `app.seed_demo`, `app.chat_cli` refuse to run unless `ENVIRONMENT=development`.
- Hardening: JSON logs with request ids (phone numbers and tokens masked), rate limits (sign-up/sign-in per address, failed logins per email, webhooks; in memory, per process), `GET /ready` (checks the DB) vs `GET /health` (does not).
- CI runs ruff, pytest, lint, typecheck, vitest and build on every push and PR.

## Hosted Qwen3: merged, and what running it for real taught us

Fuhad does not want Qwen3 on his laptop; he wants it on a **free** hosted service. That is what the demo runs on now.

- `apps/api/app/services/openai_compat.py`: `OpenAICompatibleClient` speaking `/chat/completions` (Groq, OpenRouter, Cloudflare Workers AI, vLLM...). Translates the agent's Ollama-style messages to OpenAI's (tool-call ids, JSON-string arguments, `tool` role) and back. One patient retry on 429/502/503.
- `apps/api/app/services/model.py`: `get_chat_model()` picks the client from `MODEL_PROVIDER` (`ollama` default, or `openai`).
- `app/config.py`: new settings `MODEL_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_REASONING_EFFORT`; a validator requires base URL and model when the provider is `openai`.
- `app/services/ollama.py`: `ModelError` added, `OllamaError = ModelError` kept as an alias. `app/deps.py` and `app/chat_cli.py` now use the configured model.

Merged as PR #5. Live on Groq with `qwen/qwen3.8-27b` and `LLM_REASONING_EFFORT=none`. Three things only showed up against the real host, and all three are fixed:

1. **Qwen writes tool calls badly often enough to matter.** Sometimes as malformed XML the host accepts, sometimes as a mangled *name* (`evaluate$$$$$offer`, `evaluate Offering`) that the host rejects with 400 `tool_use_failed`. PR #7 reads calls back out of `failed_generation`; PR #11 also reads a mangled name and resolves it against the tools that request actually offered, only when exactly one tool fits.
2. **Free-tier input is about 7,000 tokens/minute** for this model, roughly 1-2 buyer messages a minute. Retries wait up to 20 s, twice. A judge clicking through fast will hit it; the buyer waits, nothing is lost.
3. **A dead model must not look like a dead product.** `flow.answer_buyer` catches `ModelError`, logs it and escalates the conversation to the vendor instead of hanging.

### Choosing the free host (research on 2026-10-27, treat as unverified and recheck)

- **Groq** (OpenAI-compatible, `https://api.groq.com/openai/v1`): its models page listed one Qwen model, `qwen/qwen3.8-27b`, marked *preview*. Free-plan limits read from its rate-limits page: 30 requests/min, 1K requests/day, 8K tokens/min, 200K tokens/day. Tool-use support for that model was not stated on the page. 8K tokens/minute is tight for an agent with a system prompt plus tool rounds. Suitable for a judging demo, not for real traffic.
- **OpenRouter** `:free` routes rotate and have small daily caps.
- **Cloudflare Workers AI** has a daily free allowance; sources disagreed on context size.
- **No free always-on GPU host exists.** Colab/Kaggle sessions end; Hugging Face ZeroGPU is for Gradio demos with minutes per day. Another idea from the earlier session: Fuhad's SOVA project may have a "Rumpty" cloud server that could run Ollama.
- Check that the chosen model is really open-weight Qwen3-family (the product rule), and that tool calling works with it. Free tiers may log prompts, which contain buyer messages; mention that to Fuhad.
- Fuhad must create the provider account and API key himself and put it in `apps/api/.env` (do not ask him to paste it into chat).

Example `.env` for Groq:

```
MODEL_PROVIDER=openai
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_API_KEY=<his key>
LLM_MODEL=qwen/qwen3.8-27b
LLM_REASONING_EFFORT=none
```

## Decisions Fuhad has since made

- **Hosting: free tiers only, whole stack under N1,000.** API on Render Free (`https://sowo-api.onrender.com`), web on Vercel (`https://web-one-mu-94.vercel.app`), data on the Neon **dev** branch, Qwen3 on Groq. Fly.io was ruled out because it needs a card. Steps in `docs/DEPLOY-RENDER.md`.
- **Paystack is not used for this submission.** Payment in the demo is the bank-transfer mode (`paymentMode = "manual"`): the assistant gives the vendor's account details, the buyer says they sent it, and only the vendor's **Mark paid** makes an order paid. Paystack stays in the code as the optional path. **Do not build Paystack vendor payouts.**
- **Judges try the real thing.** `SIMULATOR_ENABLED=true` on one demo vendor, picked by `SIMULATOR_VENDOR_NAME` (config default "Ada's Footwear"); `/try` talks to that shop.

## Open decisions (Fuhad's, not yours)

- WhatsApp alert templates: Fuhad submits them in Meta Business Manager (approval takes hours to days); vendor alerts outside the 24-hour window fail without them. Code then needs the template names wired in. Nothing has been pointed at Meta's API yet.
- Migrations on Neon main: only after he says go. The demo uses the dev branch.
- Live checks against real Meta WhatsApp / Paystack have never been run; they need accounts and keys from Fuhad.
- Submission: `README.md` still has a placeholder for the demo video link before the deadline.

## Small cleanups nobody has done

- Tracked junk files (19): `apps/api/app/__pycache__/*.pyc`, `apps/api/app/services/__pycache__/*.pyc`, `apps/api/sowo.db-shm`, `sowo.db-wal`, `apps/api/sowo_api.egg-info/*`. Fix with `git rm --cached` and add patterns to `apps/api/.gitignore`.
- Rate limits are per process (fine on one machine, wrong if scaled out).
- Test data on Neon dev (shop "Preview Test Shop", product `PREVIEW-LOAF-43`, zone Ikeja) is safe to delete.

## How to run things

```bash
cd apps/api
python -m venv .venv && .venv/Scripts/activate    # Windows; use source .venv/bin/activate elsewhere
pip install -e . --group dev
pytest -q --basetemp=./.pytest-tmp                # --basetemp is needed on Windows
ruff check .                                      # `ruff format` is not used in this repo

cd ../web
pnpm install
pnpm exec vitest run && pnpm exec tsc --noEmit && pnpm exec eslint .
```

Local demo: in `apps/api/.env` set `ENVIRONMENT=development` and `SIMULATOR_ENABLED=true`, then `python -m app.seed_demo` and `uvicorn app.main:app`; in `apps/web/.env.local` set `NEXT_PUBLIC_API_URL=http://localhost:8000`. The seeded shop has no login: `python -m app.claim_vendor` gives it one.

## Gotchas learned the hard way

- Alembic runs inside `init_db()` on every start. On SQLite the migration env turns foreign keys off around the migration. A drift test (`tests/test_migrations.py`) fails if a model changes without a migration.
- `DATABASE_URL` is the pooled Neon URL; `DATABASE_URL_DIRECT` is used only for migrations.
- Next.js proxy: `/api/proxy/[...path]` only forwards an allow-list of paths (auth, conversations, delivery-zones, orders, products, simulator, vendor).
- Windows: very long shell commands with quotes fail to parse; write scripts to files instead. Files here use CRLF in places; preserve line endings when editing.
- `sowo_api.egg-info` and `__pycache__` are tracked by mistake: never commit changes to them.
- Brand/design: don't touch Fuhad's dashboard WIP files in his main checkout (`components/dashboard/*`, `app-header.tsx`, `globals.css`, `layout.tsx`) without asking.

## People and sessions

Fuhad coordinates. A "Sowo backend Python setup" Claude session coordinated merges and handled the main checkout; a Docker engineer (separate person) owns the Docker files and is being given Neon org and GitHub access by Fuhad.

## Progress log (newest last; update this whenever you finish something)

- 2026-10-27, Claude: production backend (items 1-6) merged via PR #4; main at `a4a5f9c` after the dashboard refresh.
- 2026-10-27, Claude: Fuhad decided (a) no Paystack vendor payouts, (b) Qwen3 should run on a free hosted service, not his laptop.
- 2026-10-27, Claude: wrote this handoff; added `OpenAICompatibleClient`, `get_chat_model()`, `MODEL_PROVIDER` / `LLM_*` settings on branch `feat/hosted-model` (`78c6547`).
- 2026-10-27, Claude: added `tests/test_openai_compat.py` (25 tests); documented the hosted model in `.env.example`, `apps/api/README.md` and `README.md`; reworded the payouts line as out of scope.
- 2026-10-27, Claude: opened PR #5 (`feat/hosted-model`, hosted Qwen3 + docs + payouts out of scope; 353 tests pass locally; CI was still running). Opened PR #6 (`chore/untrack-build-junk`, untracks 19 junk files). Neither is merged; both wait for CI and Fuhad's go-ahead.
- **Next steps, in order:** (1) check CI on #5 and #6 and fix anything red; (2) Fuhad creates a free hosted-Qwen3 account and puts the key in `apps/api/.env`; then run `python -m app.chat_cli` with `ENVIRONMENT=development` and `MODEL_PROVIDER=openai` and tune prompts if tool calls misbehave; (3) Fuhad decides API hosting and what judges can try; (4) migrations on Neon main only after his go-ahead; (5) fill the README placeholders (deployed URL, video link) before the deadline.
- 2026-10-27, Claude: PRs #5 and #6 merged by Fuhad. First live run against Groq (`qwen/qwen3.8-27b`) worked for a price question and a haggle (server countered N43,000 on an N35,000 offer). Found and fixed on branch `fix/hosted-tool-call-recovery`: (a) Groq answers 400 `tool_use_failed` when Qwen writes a malformed XML tool call, so the client now reads the call from `failed_generation`; (b) free-tier rate limit is 7,000 input tokens/minute (about 1,400 per model call, so roughly 1-2 buyer messages a minute): retries now wait up to 20 s, twice; (c) errors from the host now include its reason; (d) tests no longer read a developer's real `.env`.
- 2026-10-27, Claude: Fuhad's budget is under N1,000, so Fly.io (about $2.19/month, card needed) is out. Plan: API on Render's free web service (native Python, no Docker), web on Vercel, demo data on the Neon **dev** branch, Qwen3 on Groq. Steps in `docs/DEPLOY-RENDER.md`. The Docker files on `chore/api-docker` (other developer) are now optional.
- 2026-10-29, Qoder: Render Free API deployed at https://sowo-api.onrender.com; `/health` and `/ready` returned healthy before the latest `PUBLIC_BASE_URL` redeployment, which reached Live. Vercel at https://web-one-mu-94.vercel.app reached Ready after Fuhad configured the API URLs. Live sign-in, the complete simulator sale, and dashboard verification remain pending. Real WhatsApp and Paystack have not been tested; do not treat simulator checks as live payment verification. Never migrate or seed protected Neon main; only the confirmed DEV branch is authorized.
- 2026-10-29, Qoder: Added an accessible Show/Hide password eye button to the shared login/signup form on `feat/password-visibility`, preserving authentication payloads and starting masked. Checks passed in a tracked-source QA copy without dotenv files or local databases: 356 API tests, Ruff, 32 web tests, Next route type generation, TypeScript, and ESLint. The broken local pnpm launcher was bypassed using installed tool entrypoints; TypeScript passed on a sequential retry after an earlier memory failure. The local preview rendered, but browser toggle/keyboard/responsive verification remains pending because the form contained a user-entered or autofilled password; no password was revealed or submitted by automation. Keep the temporary `.qa-password-visibility` directory out of commits. This UI change still needs Fuhad's review and merge; it is not deployed.
- 2026-10-29, Qoder: **PR #9 (password toggle) merged by Fuhad.** The browser check of Show/Hide, keyboard focus and narrow screens was never done, so it is verified only by its unit tests and build, not by eye.
- 2026-10-29, Qoder: `/try` looked canned — same reply whatever the buyer typed. Two causes, neither in the agent: Render had no `SIMULATOR_VENDOR_NAME`, so `demo_vendor()` kept matching the config default "Ada's Footwear" while Fuhad's products live in his own shop, and the browser was holding a stale `sowo.try.conversation` id in `localStorage`. Setting `SIMULATOR_VENDOR_NAME` on Render and clearing that key made `/try` sell his shop with real tool calls. 356 API tests pass with a clean env; the suite is deliberately blind to a developer's `.env`.
- 2026-10-29, Qoder: **PR #10 merged** - README, `apps/api/README.md` and `docs/DEPLOY-RENDER.md` now present bank transfer as the demo's payment path with Paystack optional, and say nowhere that the AI verifies payment. Decision recorded above: no Paystack payouts, no Paystack in the submission.
- 2026-10-29, Qoder: Found the blocker for the live sale. Every haggle died: Qwen3 wrote the tool name as `evaluate$$$$$offer` / `evaluate Offering`, Groq answered 400 `tool_use_failed` with the arguments intact and the name unusable, PR #7's recovery regex accepted only a clean identifier, so the client raised `ModelError` and the buyer got "Sorry, something went wrong on my side" while the conversation flipped to NEEDS ATTENTION. Fix on `fix/mangled-tool-call-recovery` (PR #11): widen the name group and resolve the name against the tools that request offered, only when exactly one fits, so ambiguous or unknown names still reach the agent's own rejection. 360 API tests and `ruff check` pass. **Not yet proved live** - needs the merge, a Render redeploy, and the walkthrough below run again.
- 2026-10-29, Qoder: **Skipped deliberately:** the optional AI receipt-check vision helper. Its own gate was "only start with more than 18 hours left"; there were about 14. It is not in the repo and is not claimed anywhere. Fuhad's instruction stands that a screenshot proves nothing: only **Mark paid** (or a verified Paystack webhook) may move an order to paid, and the guard blocking the model from announcing payment is unchanged.
- **Still to do before submitting:** (1) merge PR #11 and redeploy Render; (2) walk `/try` end to end - black loafers size 43, haggle, "Ikeja", account details, "I've sent the transfer", then **Mark paid** in `/dashboard` - and report anything that misbehaves; the bank fields in `/dashboard/settings` have never been rendered under automation (React's `onChange` did not fire from the driven radio), so Fuhad entered them by hand with invented details; (3) fill the demo video link in `README.md`; (4) nothing has been checked against Meta WhatsApp or Paystack. Keep `.qa-bank-transfer/`, `.qa-password-visibility/`, `.claude/` and `docs/tasks/` out of commits.
