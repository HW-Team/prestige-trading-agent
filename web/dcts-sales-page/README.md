# DCTS production sales page

Dependency-light static sales page for the regulated Thai DCTS trading-education offer. It preserves the approved legacy brand while keeping payment verification, signed submissions, access provisioning, and all secrets outside browser code.

## Status

The page is intentionally **configuration-ready, not commercially live**. The displayed `3,990 THB` is a provisional draft price and is labelled `รอยืนยันราคาและเงื่อนไข`. Checkout, VSL, support, policy, legal-entity, coach, LMS, evidence, and consented testimonial details are pending approval. With the checked-in empty `config.js`, conversion opens a clear pending dialog and cannot navigate or collect payment.

## Public runtime configuration

Copy `config.example.js` to a deploy-managed `config.js` and replace only approved public HTTPS URLs:

- `checkoutUrl`: must use `https://buy.stripe.com` or `https://checkout.stripe.com`
- `supportUrl`
- `vslUrl`
- `privacyPolicyUrl`
- `termsUrl`
- `termsSaleUrl`
- `refundPolicyUrl`

`config.js` is delivered to every visitor. Never put credentials, signing material, administrative values, private community links, or other secrets in it. Checkout handoff preserves only `utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, and `utm_term`, each capped at 200 characters.

## Serve locally

```bash
python3 -m http.server 8788 --bind 127.0.0.1 --directory web/dcts-sales-page
```

Open `http://127.0.0.1:8788/`. This local server is for QA only. A future deployment must set reviewed security headers at the CDN or static host in addition to the document policy.

## Validate

```bash
python3 web/dcts-sales-page/scripts/validate.py
NODE_PATH=/opt/data/profiles/rook-hw-team/node_modules node web/dcts-sales-page/scripts/browser-qa.js
```

Browser QA expects the local server above and writes deterministic screenshots to `web/dcts-sales-page/qa/` for 390x844, 768x1024, and 1440x900 viewports.

Trirong, Sarabun, Montserrat, and Playfair Display are self-hosted from the Google Fonts repository under the SIL Open Font License. The corresponding license texts are stored beside the font files in `assets/fonts/`.

## Deployment checklist

1. Obtain approval for every public URL and all legal/business copy.
2. Confirm the final price and replace the provisional label only after written approval.
3. Replace pending Coach, LMS, evidence, and testimonial slots only with reviewed assets and consent.
4. Generate deploy-time `config.js` without changing `config.example.js`.
5. Configure CSP and other security headers at the hosting edge.
6. Run static validation and browser QA against the exact deploy artifact.
7. Verify that checkout reaches the approved Stripe host and that payment/access confirmation remains server-side.
