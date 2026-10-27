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

## In progress: hosted Qwen3 (branch `feat/hosted-model`, NOT merged)

Fuhad does not want Qwen3 on his laptop; he wants it on a **free** hosted service. Work started:
- `apps/api/app/services/openai_compat.py`: `OpenAICompatibleClient` speaking `/chat/completions` (Groq, OpenRouter, Cloudflare Workers AI, vLLM...). Translates the agent's Ollama-style messages to OpenAI's (tool-call ids, JSON-string arguments, `tool` role) and back. One patient retry on 429/502/503.
- `apps/api/app/services/model.py`: `get_chat_model()` picks the client from `MODEL_PROVIDER` (`ollama` default, or `openai`).
- `app/config.py`: new settings `MODEL_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_REASONING_EFFORT`; a validator requires base URL and model when the provider is `openai`.
- `app/services/ollama.py`: `ModelError` added, `OllamaError = ModelError` kept as an alias. `app/deps.py` and `app/chat_cli.py` now use the configured model.
- The existing 328 API tests and ruff pass with these changes.

Done on this branch since the first handoff (see the progress log at the bottom): tests (`tests/test_openai_compat.py`), `.env.example`, both READMEs, and the Paystack-payouts line. What is left is only: open/merge the PR, then a real run against a hosted Qwen3 once Fuhad has an account and key.

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

## Open decisions (Fuhad's, not yours)

- **API hosting target** (undecided). Suggestion: Fly.io `lhr` for the API (near Neon London) and Vercel for web. Web needs `NEXT_PUBLIC_API_URL` and `API_INTERNAL_URL`. Set `CLIENT_IP_HEADER=x-forwarded-for` only if the API is reachable solely through the web proxy.
- **What judges can try.** With the simulator off and no hosted Qwen3, a production deploy shows only a signup page. Options: (a) a separate public demo deploy in mock mode (no `NEXT_PUBLIC_API_URL`) for `/try`; (b) the real API with `SIMULATOR_ENABLED=true` on one demo vendor (contradicts "no more demo").
- `apps/web/components/app-header.tsx` has a Buyer/Vendor switch linking to `/try`, which 404s when the simulator is off. Fuhad's file.
- Migrations on Neon main: only after hosting is decided and he says go.
- WhatsApp alert templates: Fuhad submits them in Meta Business Manager (approval takes hours to days); vendor alerts outside the 24-hour window fail without them. Code then needs the template names wired in.
- Live checks against real Qwen3 / Meta WhatsApp / Paystack have never been run. They need accounts and keys from Fuhad. Expect prompt tuning on the first real run.
- Submission: `README.md` lines ~38-39 still say to add the deployed URL and the video link before submission.

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
