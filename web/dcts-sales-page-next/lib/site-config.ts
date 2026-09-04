/**
 * Client-safe public configuration.
 * Only NEXT_PUBLIC_* values live here — never secrets.
 * Mirrors the old static page's config.js.
 */
export const siteConfig = {
  checkoutUrl: process.env.NEXT_PUBLIC_CHECKOUT_URL ?? "",
  supportUrl: process.env.NEXT_PUBLIC_SUPPORT_URL ?? "",
  vslUrl: process.env.NEXT_PUBLIC_VSL_URL ?? "",
  privacyPolicyUrl: process.env.NEXT_PUBLIC_PRIVACY_POLICY_URL ?? "",
  termsUrl: process.env.NEXT_PUBLIC_TERMS_URL ?? "",
  termsSaleUrl: process.env.NEXT_PUBLIC_TERMS_SALE_URL ?? "",
  refundPolicyUrl: process.env.NEXT_PUBLIC_REFUND_POLICY_URL ?? "",
} as const;
