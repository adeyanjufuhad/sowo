# Deploying Sowo for free: API on Render, web on Vercel, data on Neon

Cost: ₦0. Everything below uses free tiers, and none of it needs a Docker image (Render builds the Python app itself).
Written 2026-10-27. Free-tier terms change, so read the plan screen when you sign up and don't enter a card unless
something asks for one.

What runs where:

| Part | Where | Free-tier limits that matter |
| --- | --- | --- |
| API (`apps/api`) | Render free web service | Sleeps after 15 minutes without traffic, wakes in about a minute. 750 instance hours a month (enough for one service all month). No persistent disk, which is fine: data lives in Neon. |
| Web (`apps/web`) | Vercel (already connected to this repo) | Hobby plan |
| Database | Neon, **dev** branch | Free plan. Keep branch `main` empty for real vendors later |
| Qwen3 | Groq | About 7,000 input tokens a minute: one or two buyer messages a minute |

This is the public demo deployment: simulator on, one demo shop ("Ada's Footwear"), on the Neon **dev** branch so
nothing here touches the branch reserved for real vendors.

## 1. Put the demo shop in the Neon dev branch (once, on your own computer)

The API creates the tables itself when it starts. The demo shop's products and delivery areas come from the seed
command, which refuses to run unless `ENVIRONMENT=development`. Run it from a terminal, against the dev branch only:

```powershell
cd apps\api
$env:ENVIRONMENT = "development"
$env:DATABASE_URL = "<Neon dev branch, pooled connection string>"
$env:DATABASE_URL_DIRECT = "<Neon dev branch, direct connection string>"
.venv\Scripts\python -m app.seed
.venv\Scripts\python -m app.claim_vendor "Ada's Footwear" demo@yourdomain.example   # asks for a password
```

Copy the two strings from the Neon console (branch **dev** → Connect). Check the branch name before you run it.
Never run this against branch `main`. Close the terminal afterwards so the values go away.

`claim_vendor` gives the demo shop a dashboard login. If you want judges to see the dashboard, put that email and
password in the README as demo credentials (it is demo data only). Use a password you use nowhere else.

## 2. Create the API on Render

1. Sign up at render.com with GitHub.
2. **New → Web Service**, choose the repository `adeyanjufuhad/sowo`.
3. Settings:
   - Name: `sowo-api`
   - Region: Frankfurt (closest to Neon in London)
   - Branch: `main`
   - Root Directory: `apps/api`
   - Runtime: Python 3
   - Build Command: `pip install .`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Instance Type: **Free**
   - Health Check Path: `/health`
4. Environment variables (Environment tab). Type or paste the values in Render's page, never into chat or git:

   | Name | Value |
   | --- | --- |
   | `DATABASE_URL` | Neon dev branch, **pooled** string |
   | `DATABASE_URL_DIRECT` | Neon dev branch, **direct** string |
   | `SIMULATOR_ENABLED` | `true` |
   | `MODEL_PROVIDER` | `openai` |
   | `LLM_BASE_URL` | `https://api.groq.com/openai/v1` |
   | `LLM_API_KEY` | your Groq key |
   | `LLM_MODEL` | `qwen/qwen3.8-27b` (or the Qwen3 id Groq lists) |
   | `LLM_REASONING_EFFORT` | `none` |
   | `PUBLIC_BASE_URL` | the Render address, such as `https://sowo-api.onrender.com` |
   | `CORS_ORIGINS` | the web app's address, such as `https://sowo.vercel.app` |
   | `SIMULATOR_VENDOR_NAME` | optional. The shop `/try` sells, matched on its exact name. Unset, it is the seeded
   `Ada's Footwear`; point it at your own shop's name to demo with your own catalog. Changing it needs a redeploy. |

   Leave `ENVIRONMENT` unset (it defaults to `production`; the log will warn that the simulator is on, which is
   expected here). Leave `CLIENT_IP_HEADER` unset: the API is public, so a forwarded address could be faked. Leave the
   WhatsApp and Paystack variables unset until you have real accounts — a demo does not need them, because the shop can
   take payment by bank transfer instead (see step 5).
5. Create the service. When the build finishes, open `https://<your-service>.onrender.com/ready`. It should say
   `{"status":"ready"}`. If the build fails on a package, add `PYTHON_VERSION` (CI uses 3.12) and redeploy.

## 3. Point the web app at it (Vercel)

In the Vercel project for `apps/web`, open **Settings → Environment Variables** and add, for Production and Preview:

| Name | Value |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | the Render address, no trailing slash |
| `API_INTERNAL_URL` | the same address |

`NEXT_PUBLIC_` values are baked in at build time, so **redeploy** the web project afterwards (Deployments → the
latest → Redeploy). Then open `/try` on the live site and chat.

## 4. Keep the API awake

Render's free service sleeps after 15 minutes. A free uptime monitor (for example UptimeRobot) that requests
`https://<your-service>.onrender.com/health` every 5–10 minutes keeps it awake, and one service running all month
fits inside the 750 free hours. `/health` never touches the database, so Neon can still sleep. Do not point it at
`/ready`. Skip this step if you'd rather accept a one-minute first load.

## 5. Check it

- `/ready` says ready.
- Sign in and open **Shop settings**. Under *How buyers pay you*, choose **Bank transfer** and fill in the account
  fields. This is a public demo, so use details that belong to nobody: a made-up bank name, a made-up account name and
  a made-up 10-digit number. Save. (Paystack is the other option and needs its keys; the demo does not need them.)
- Open **Catalog** and add at least one delivery area with a fee, such as Ikeja. Without one Sowo cannot price a
  delivery, and the sale stops at the haggle.
- `/try` on the live web app: ask for the black loafers in size 43, haggle, give "Ikeja" as the area. Sowo quotes the
  total and gives the account details with the order reference for the narration. Tap **I've sent the transfer**.
- Back in the dashboard: the order is still waiting, because a buyer's word is not payment. Tap **Mark paid**. The
  order goes to `PAID` and the buyer gets a receipt written by the server, not by the model.
- `/login` with the demo shop's email and password shows the chat, the order and the catalog.
- Wait 20 minutes without using it, then reload: it should wake within about a minute.

## Limits to remember

- Groq's free token limit is the bottleneck. Space messages out, or the reply is "Sorry, something went wrong".
- Nothing here is for real buyers: the simulator endpoints have no sign-in, and the demo data is public.
- Real WhatsApp needs a Meta number, approved message templates and `WHATSAPP_*` variables. Paystack needs its keys.
  Bank transfer needs neither, which is why the demo runs on it.
