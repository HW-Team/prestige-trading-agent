const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const baseUrl = process.env.DCTS_QA_URL || "http://127.0.0.1:8788/";
const outDir = path.resolve(__dirname, "../qa");
fs.mkdirSync(outDir, { recursive: true });

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

async function observe(page, bucket) {
  const expectedOrigin = new URL(baseUrl).origin;
  page.on("request", (request) => {
    if (new URL(request.url()).origin !== expectedOrigin) bucket.push(`external request: ${request.url()}`);
  });
  page.on("console", (message) => {
    if (message.type() === "error") bucket.push(`console: ${message.text()}`);
  });
  page.on("pageerror", (error) => bucket.push(`pageerror: ${error.message}`));
  page.on("requestfailed", (request) => bucket.push(`request: ${request.url()} ${request.failure()?.errorText || "failed"}`));
  page.on("response", (response) => {
    if (response.status() >= 400) bucket.push(`response: ${response.status()} ${response.url()}`);
  });
}

async function inspectViewport(browser, name, viewport, options = {}) {
  const issues = [];
  const context = await browser.newContext({
    viewport,
    reducedMotion: options.reducedMotion ? "reduce" : "no-preference",
  });
  const page = await context.newPage();
  await observe(page, issues);
  const response = await page.goto(baseUrl, { waitUntil: "networkidle", timeout: 30000 });
  assert(response && response.status() === 200, `${name}: expected HTTP 200`);
  await page.evaluate(() => document.fonts.ready);
  await page.locator("img").evaluateAll((images) => Promise.all(images.map((image) => {
    image.loading = "eager";
    if (image.complete) return Promise.resolve();
    return new Promise((resolve) => {
      image.addEventListener("load", resolve, { once: true });
      image.addEventListener("error", resolve, { once: true });
    });
  })));

  const state = await page.evaluate(() => {
    const heroCta = document.querySelector(".hero [data-open-signup]").getBoundingClientRect();
    const nav = document.querySelector(".nav-wrap").getBoundingClientRect();
    const bodyFont = getComputedStyle(document.body).fontFamily;
    const headingFont = getComputedStyle(document.querySelector("h1")).fontFamily;
    return {
      overflow: document.documentElement.scrollWidth > window.innerWidth,
      heroCtaVisible: heroCta.top >= 0 && heroCta.bottom <= window.innerHeight,
      missingImages: [...document.images].filter((image) => !image.complete || image.naturalWidth === 0).map((image) => image.src),
      navHeight: Math.round(nav.height),
      bodyFont,
      headingFont,
      configState: document.getElementById("checkout-button")?.dataset.configState,
      invalidCheckoutAccepted: window.DCTS_INTERNALS.isApprovedCheckoutUrl("http://buy.stripe.com/not-secure") || window.DCTS_INTERNALS.isApprovedCheckoutUrl("https://example.com/not-stripe"),
      validCheckoutAccepted: window.DCTS_INTERNALS.isApprovedCheckoutUrl("https://buy.stripe.com/test"),
      preservedUrl: window.DCTS_INTERNALS.buildCheckoutUrl("https://buy.stripe.com/test", "?utm_source=qa&utm_campaign=safe&unexpected=drop")?.href,
    };
  });
  assert(!state.overflow, `${name}: horizontal overflow`);
  assert(state.missingImages.length === 0, `${name}: missing images ${state.missingImages.join(", ")}`);
  assert(state.navHeight <= 80, `${name}: navigation exceeds 80px`);
  assert(state.bodyFont.includes("Sarabun"), `${name}: Sarabun did not load`);
  assert(state.headingFont.includes("Trirong"), `${name}: Trirong did not load`);
  assert(state.configState === "pending", `${name}: empty config must be pending`);
  assert(!state.invalidCheckoutAccepted && state.validCheckoutAccepted, `${name}: checkout host validation failed`);
  assert(state.preservedUrl.includes("utm_source=qa") && state.preservedUrl.includes("utm_campaign=safe") && !state.preservedUrl.includes("unexpected"), `${name}: UTM allowlist failed`);
  if (viewport.width === 390) assert(state.heroCtaVisible, `${name}: hero CTA is not in the first viewport`);

  if (viewport.width < 960) {
    const menu = page.locator(".menu-toggle");
    await menu.click();
    assert(await menu.getAttribute("aria-expanded") === "true", `${name}: mobile menu did not open`);
    await page.keyboard.press("Escape");
    assert(await menu.getAttribute("aria-expanded") === "false", `${name}: mobile menu did not close with Escape`);
  } else {
    const desktopNav = page.locator(".desktop-nav");
    assert(await desktopNav.evaluate((element) => element.scrollHeight === element.clientHeight), `${name}: desktop navigation wrapped`);
  }

  const moduleButton = page.locator("#curriculum .module button").nth(1);
  await moduleButton.click();
  assert(await moduleButton.getAttribute("aria-expanded") === "true", `${name}: curriculum accordion failed`);
  assert(Boolean(await moduleButton.getAttribute("aria-controls")), `${name}: accordion control relationship missing`);

  const faqButton = page.locator("#faq .faq-item button").first();
  await faqButton.click();
  assert(await faqButton.getAttribute("aria-expanded") === "true", `${name}: FAQ accordion failed`);

  const signupTrigger = page.locator(".hero [data-open-signup]");
  await signupTrigger.click();
  const signup = page.locator("#signup-modal");
  assert(await signup.isVisible(), `${name}: signup dialog did not open`);
  assert(await signup.locator("#form-status").textContent().then((text) => text.includes("ยังรอ URL")), `${name}: pending checkout explanation missing`);
  assert(await signup.locator("#checkout-button").isDisabled(), `${name}: checkout must be disabled without configuration`);
  await page.waitForFunction(() => document.activeElement?.closest("#signup-modal") !== null, null, { timeout: 1000 });
  await page.keyboard.press("Escape");
  assert(await signup.isHidden(), `${name}: signup dialog did not close with Escape`);
  assert(await signupTrigger.evaluate((element) => document.activeElement === element), `${name}: signup focus was not restored`);

  await page.locator(".hero [data-open-video]").first().click();
  const video = page.locator("#video-modal");
  assert(await video.isVisible(), `${name}: video dialog did not open`);
  assert(await video.locator("#video-status").textContent().then((text) => text.includes("ยังรอ URL")), `${name}: pending VSL explanation missing`);
  const close = video.locator(".modal-close");
  await close.focus();
  await page.keyboard.press("Shift+Tab");
  assert(await page.evaluate(() => document.activeElement?.closest("#video-modal") !== null), `${name}: reverse focus trap failed`);
  await page.keyboard.press("Escape");

  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(150);
  await page.screenshot({ path: path.join(outDir, `${name}.png`), fullPage: false });

  if (viewport.width === 390) {
    await page.evaluate(() => window.scrollTo(0, document.querySelector(".hero").offsetHeight + 200));
    await page.waitForTimeout(150);
    assert(await page.locator(".sticky-cta").evaluate((element) => element.classList.contains("is-visible")), `${name}: sticky CTA did not appear after hero`);
  }

  await context.close();
  assert(issues.length === 0, `${name}: browser issues: ${issues.join(" | ")}`);
  return state;
}

(async () => {
  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
  try {
    const results = {};
    results.mobile = await inspectViewport(browser, "mobile-390x844", { width: 390, height: 844 });
    results.tablet = await inspectViewport(browser, "tablet-768x1024", { width: 768, height: 1024 });
    results.desktop = await inspectViewport(browser, "desktop-1440x900", { width: 1440, height: 900 });
    results.narrow = await inspectViewport(browser, "edge-320x700", { width: 320, height: 700 });
    results.reducedMotion = await inspectViewport(browser, "reduced-motion-390x844", { width: 390, height: 844 }, { reducedMotion: true });
    console.log(JSON.stringify({ ok: true, baseUrl, screenshots: 5, results }, null, 2));
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
