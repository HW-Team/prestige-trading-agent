# Webhook examples

All bodies must be sent byte-for-byte with their provider signature.

## Meta verification
`GET /webhooks/meta?hub.mode=subscribe&hub.verify_token=TOKEN&hub.challenge=123`

## Organic Messenger DM
```json
{"object":"page","entry":[{"messaging":[{"sender":{"id":"PSID"},"recipient":{"id":"PAGE"},"timestamp":1,"message":{"mid":"m_1","text":"I am new"}}]}]}
```
Header: `X-Hub-Signature-256: sha256=<HMAC-SHA256(body, META_APP_SECRET)>`.

## Lead Ad
```json
{"object":"page","entry":[{"changes":[{"field":"leadgen","value":{"leadgen_id":"123","page_id":"page","form_id":"form"}}]}]}
```

## Form completion
```json
{"submission_id":"form_123","external_id":"PSID","email":"person@example.com","path":"newbie","data":{}}
```
Header: `X-Form-Signature: <HMAC-SHA256(body, FORM_WEBHOOK_SECRET)>`.

## Stripe
Forward Stripe's unmodified payload to `/webhooks/stripe` with its `Stripe-Signature` header. Test locally with `stripe listen --forward-to localhost:8000/webhooks/stripe`.
