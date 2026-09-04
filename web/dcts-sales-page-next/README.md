# DCTS Sales Page — Next.js (App Router)

Production frontend for the regulated Thai DCTS trading-education offer.
Ported from the static page (`web/dcts-sales-page`) into **Next.js 16 + TypeScript**
so the funnel can connect to the backend from day one.

## What connects where

```
Browser (this app)
 ├─ POST /api/leads     → signs (HMAC-SHA256) + forwards to FastAPI backend
 │                        POST /webhooks/form  (prestige-trading-agent)
 ├─ POST /api/checkout  → creates Stripe Checkout Session server-side
 │                        (metadata: name, phone, email + UTM)
 └─ GET  /              → static prerendered landing (SEO-safe)
```

- The HMAC signing secret and Stripe key **never** reach the browser.
- `/api/checkout` falls back to the approved `NEXT_PUBLIC_CHECKOUT_URL`
  (buy.stripe.com) when Stripe is not configured yet — same guard the static
  page had. Without any config it returns `{ mode: "pending" }` and the button
  stays disabled.
- Signup modal collects ชื่อ / เบอร์โทร / อีเมล (funnel ข้อมูลหลังบ้าน);
  consent must be checked before checkout is enabled.

## Env

Copy `.env.example` → `.env.local` (local) or set in Coolify (deploy):

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_CHECKOUT_URL` | Approved Stripe Payment Link (fallback) |
| `NEXT_PUBLIC_SUPPORT_URL` / `VSL_URL` / policy URLs | Footer/modal links (public) |
| `STRIPE_SECRET_KEY` + `STRIPE_PRICE_ID` | Enables server-side Checkout Session |
| `PRESTIGE_BACKEND_URL` | FastAPI base, e.g. `https://api.example.com` |
| `PRESTIGE_FORM_WEBHOOK_SECRET` | Must equal backend `PRESTIGE_FORM_WEBHOOK_SECRET` |

## Run / build

```bash
npm install
npm run dev        # http://localhost:3000
npm run build      # note: this box is RAM-tight — use:
NODE_OPTIONS="--max-old-space-size=1536" npx next build --webpack
npm run start
```

## Compliance notes (unchanged from static page)

- No profit guarantees, no fake testimonials, no fabricated statistics.
- Price `3,990 THB` is provisional and labelled `รอยืนยันราคาและเงื่อนไข`.
- Secrets, signing material, private room links stay server-side.
- CSP + security headers set in `next.config.ts`.
- Client interacts only with same-origin `/api/*`; payment confirmation and
  access provisioning happen in the backend webhooks.
