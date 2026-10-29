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

## 6. Connect WhatsApp (optional, live demo)

The API already speaks Meta's Cloud API: it checks every delivery's signature, reads buyer messages (text or a
picture), answers from the vendor's own number and marks the message read. `tests/test_whatsapp.py` covers the
handshake, a forged body, a repeated delivery, echo mode and a Meta outage. What is left is all on Meta's side, so
this is setting, not code.

1. **developers.facebook.com** → My Apps → Create app → use case **Connect on WhatsApp** → link your Meta Business
   account. Meta gives you a free **test number**. Business verification is not needed for it.
2. **Use cases → Customize → Basic setup → Step 1. Try it out**. The app sidebar no longer has a *WhatsApp* item;
   the test number, the Phone number ID and the WhatsApp Business Account ID all live here. Add your own phone under
   *To* → *Manage phone number list* and accept the code it sends in WhatsApp. A test number can message **five**
   verified numbers, and only those numbers can message it.
3. Collect three values. Type them into Render and the dashboard yourself; never into chat, a commit or an issue:
   - *App Secret*: App settings → Basic
   - *Phone number ID*: Step 1. Try it out (digits only)
   - a **permanent** token: Business settings → System users → Add → generate with `whatsapp_business_management`
     and `whatsapp_business_messaging`. The 24-hour token on the API Setup page dies mid-demo; do not use it.
4. **Render → sowo-api → Environment**, add and let it redeploy:

   | Name | Value |
   | --- | --- |
   | `WHATSAPP_ACCESS_TOKEN` | the permanent token |
   | `WHATSAPP_APP_SECRET` | the app secret |
   | `WHATSAPP_VERIFY_TOKEN` | any random phrase you invent; you paste the same phrase into Meta |

5. **Use cases → Customize → Basic setup → Step 2. Production setup → Configure Webhooks**: Callback URL
   `https://<your-service>.onrender.com/webhooks/whatsapp`, paste your verify token, **Verify and save**, then in
   **Webhook fields** switch **messages** to **Subscribed**. Verification fails with 403 if the token differs, and
   the API answers 503 while `WHATSAPP_APP_SECRET` is unset. A wrong App Secret still verifies (the handshake does
   not use it) but every delivery then comes back 403, so watch the Render log for `POST /webhooks/whatsapp`.
6. **Publish the app** (App settings → Publish). While the app is unpublished Meta delivers only the *Test webhooks*
   samples from the dashboard: real messages are not sent to your callback at all, not even from your own verified
   number, and nothing appears in the Render log. Publishing needs a **Privacy policy URL**; the site serves one at
   `/privacy`.
7. **Attach the app to the WhatsApp Business Account.** The *Subscribed* switch in step 5 covers the webhook fields
   on the app; it does not attach the app to the account. Without that attachment Meta accepts your callback and
   *Test* works, but a real message never reaches it and nothing appears in the Render log — even published. Check it
   in **Tools → Graph API Explorer** (use the token the page fills in; do not copy it anywhere):
   `GET /{WhatsApp Business Account ID}/subscribed_apps` must list your app by name. If only
   `WA DevX Webhook Events 1P App` is there, switch the method to **POST** on the same path and **Submit**; the reply
   is `{"success": true}` and the next real message arrives.
8. **Dashboard → Shop settings**: paste the Phone number ID into *WhatsApp phone number ID* and your phone into
   *Alert phone*. It should say connected.
9. Message the test number from your phone. A `POST /webhooks/whatsapp` 200 shows up in the Render log within a
   second or two, the buyer gets Sowo's reply, and the chat appears in the dashboard.

   A 200 followed by `WhatsApp messages failed: Client error '401 Unauthorized'` means the delivery worked and the
   token did not: it expired, or was pasted with a newline. Sowo still writes the reply and it shows in the
   dashboard, but the buyer never receives it. Generate a fresh permanent token (step 3) and update
   `WHATSAPP_ACCESS_TOKEN`.

   A 200 followed by `WhatsApp accepted a reply for …` and then `WhatsApp delivery to … failed: 131031: Business
   Account locked` is Meta refusing to carry the message: the WhatsApp Business Account is restricted until the
   business is verified. WhatsApp Manager → Overview says *Account Restricted — you will need to verify your
   business*. The fix is Business settings → Security Center → Business Verification → **Start verification**, which
   wants the business's legal details and documents and takes as long as Meta takes; a fresh account rarely clears
   it the same evening. Until it does, buyers' messages still arrive, Sowo still answers and the chat still appears
   in the dashboard — only Meta's last hop to the buyer's phone is blocked. Plan the demo on `/try` and the
   dashboard, not on the reply landing in someone's WhatsApp.

To check the wiring without spending model quota, set `WHATSAPP_ECHO_MODE=true` on Render: the API then answers
`Echo: <what the buyer typed>` and never calls the model. Turn it off afterwards.

**Alerts to your own phone will not arrive** until a utility template is approved, because an alert you send to
yourself is business-initiated and Meta only accepts approved templates outside a 24-hour window opened by that
person messaging you. Buyer replies are always inside the window the buyer opens, so they do arrive. For a demo,
watch the dashboard for new orders.

## Limits to remember

- Groq's free token limit is the bottleneck. Space messages out, or the reply is "Sorry, something went wrong".
- Nothing here is for real buyers: the simulator endpoints have no sign-in, and the demo data is public.
- Real WhatsApp needs a Meta app, a number and the `WHATSAPP_*` variables (step 6); buyer replies then work at once,
  vendor alerts need an approved template. Paystack needs its keys. Bank transfer needs neither, which is why the demo
  runs on it.
