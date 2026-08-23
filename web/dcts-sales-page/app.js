(() => {
  "use strict";

  const APPROVED_CHECKOUT_HOSTS = new Set(["buy.stripe.com", "checkout.stripe.com"]);
  const APPROVED_UTM_KEYS = ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"];
  const config = window.DCTS_CONFIG && typeof window.DCTS_CONFIG === "object" ? window.DCTS_CONFIG : {};

  function parseHttpsUrl(value) {
    if (typeof value !== "string" || !value.trim()) return null;
    try {
      const url = new URL(value.trim());
      if (url.protocol !== "https:" || url.username || url.password) return null;
      return url;
    } catch {
      return null;
    }
  }

  function isApprovedCheckoutUrl(value) {
    const url = parseHttpsUrl(value);
    return Boolean(url && APPROVED_CHECKOUT_HOSTS.has(url.hostname));
  }

  function buildCheckoutUrl(value, currentSearch = window.location.search) {
    if (!isApprovedCheckoutUrl(value)) return null;
    const checkout = new URL(value.trim());
    const incoming = new URLSearchParams(currentSearch);
    APPROVED_UTM_KEYS.forEach((key) => {
      const valueToCopy = incoming.get(key);
      if (valueToCopy && valueToCopy.length <= 200) checkout.searchParams.set(key, valueToCopy);
    });
    return checkout;
  }

  window.DCTS_INTERNALS = Object.freeze({ isApprovedCheckoutUrl, buildCheckoutUrl });

  const body = document.body;
  const menuButton = document.querySelector(".menu-toggle");
  const mobileMenu = document.getElementById("mobile-menu");
  const hero = document.querySelector(".hero");
  const stickyCta = document.querySelector(".sticky-cta");
  const videoModal = document.getElementById("video-modal");
  const signupModal = document.getElementById("signup-modal");
  const consent = document.getElementById("checkout-consent");
  const checkoutButton = document.getElementById("checkout-button");
  const formStatus = document.getElementById("form-status");
  const videoStatus = document.getElementById("video-status");
  const videoLink = document.getElementById("video-link");
  let activeModal = null;
  let lastFocused = null;

  document.querySelectorAll("[data-fallback-image]").forEach((image) => {
    image.addEventListener("error", () => {
      image.hidden = true;
    });
  });

  function setMenu(open) {
    if (!menuButton || !mobileMenu) return;
    menuButton.setAttribute("aria-expanded", String(open));
    mobileMenu.hidden = !open;
  }

  menuButton?.addEventListener("click", () => {
    setMenu(menuButton.getAttribute("aria-expanded") !== "true");
  });
  mobileMenu?.querySelectorAll("a").forEach((link) => link.addEventListener("click", () => setMenu(false)));

  const focusableSelector = [
    "button:not([disabled])",
    "a[href]:not([aria-disabled=\"true\"])",
    "input:not([disabled])",
    "[tabindex]:not([tabindex=\"-1\"])",
  ].join(",");

  function openModal(modal) {
    if (!modal) return;
    if (activeModal) closeModal(false);
    lastFocused = document.activeElement;
    activeModal = modal;
    modal.hidden = false;
    body?.classList.add("modal-open");
    requestAnimationFrame(() => modal.querySelector(".modal-card")?.focus());
  }

  function closeModal(restoreFocus = true) {
    if (!activeModal) return;
    activeModal.hidden = true;
    activeModal = null;
    body?.classList.remove("modal-open");
    if (restoreFocus && lastFocused instanceof HTMLElement) lastFocused.focus();
  }

  document.querySelectorAll("[data-open-video]").forEach((button) => {
    button.addEventListener("click", () => openModal(videoModal));
  });
  document.querySelectorAll("[data-open-signup]").forEach((button) => {
    button.addEventListener("click", () => openModal(signupModal));
  });
  document.querySelector("[data-switch-signup]")?.addEventListener("click", () => {
    closeModal(false);
    openModal(signupModal);
  });
  document.querySelectorAll("[data-close-modal]").forEach((button) => {
    button.addEventListener("click", () => closeModal());
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      if (activeModal) closeModal();
      else if (mobileMenu && !mobileMenu.hidden) setMenu(false);
      return;
    }
    if (event.key !== "Tab" || !activeModal) return;
    const focusable = [...activeModal.querySelectorAll(focusableSelector)];
    if (!focusable.length) {
      event.preventDefault();
      activeModal.querySelector(".modal-card")?.focus();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && (document.activeElement === first || document.activeElement === activeModal.querySelector(".modal-card"))) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  document.querySelectorAll("[data-accordion-group]").forEach((group, groupIndex) => {
    group.querySelectorAll("article > h3 > button").forEach((button, itemIndex) => {
      const item = button.closest("article");
      const panel = item?.querySelector(".accordion-panel");
      if (!item || !panel) return;
      if (!panel.id) panel.id = `accordion-${groupIndex}-${itemIndex}`;
      button.setAttribute("aria-controls", panel.id);
      button.addEventListener("click", () => {
        const isOpen = button.getAttribute("aria-expanded") === "true";
        button.setAttribute("aria-expanded", String(!isOpen));
        item.classList.toggle("is-open", !isOpen);
        panel.hidden = isOpen;
      });
    });
  });

  if (hero && stickyCta && "IntersectionObserver" in window) {
    const stickyButton = stickyCta.querySelector("button");
    const observer = new IntersectionObserver(([entry]) => {
      const visible = !entry.isIntersecting;
      stickyCta.classList.toggle("is-visible", visible);
      stickyCta.setAttribute("aria-hidden", String(!visible));
      if (stickyButton) stickyButton.tabIndex = visible ? 0 : -1;
    }, { threshold: 0.08 });
    observer.observe(hero);
  }

  const checkoutReady = isApprovedCheckoutUrl(config.checkoutUrl);
  function updateCheckoutState() {
    if (!checkoutButton || !consent || !formStatus) return;
    checkoutButton.disabled = !checkoutReady || !consent.checked;
    checkoutButton.dataset.configState = checkoutReady ? "ready" : "pending";
    formStatus.textContent = checkoutReady
      ? (consent.checked ? "พร้อมส่งต่อไปยังหน้าชำระเงินของ Stripe" : "โปรดอ่านและยืนยันข้อมูลก่อนดำเนินการ")
      : "ระบบชำระเงินยังรอ URL ที่ได้รับอนุมัติ จึงยังไม่สามารถดำเนินการต่อได้";
  }
  consent?.addEventListener("change", updateCheckoutState);
  checkoutButton?.addEventListener("click", () => {
    const destination = buildCheckoutUrl(config.checkoutUrl);
    if (!destination || !consent?.checked) {
      updateCheckoutState();
      return;
    }
    window.location.assign(destination.href);
  });
  updateCheckoutState();

  const approvedVsl = parseHttpsUrl(config.vslUrl);
  if (videoLink && videoStatus) {
    if (approvedVsl) {
      videoLink.href = approvedVsl.href;
      videoLink.hidden = false;
      videoStatus.textContent = "เปิดวิดีโอคำอธิบายที่ได้รับอนุมัติในแท็บใหม่";
    } else {
      videoLink.hidden = true;
      videoStatus.textContent = "วิดีโอยังรอ URL ที่ได้รับอนุมัติ";
    }
  }

  const publicLinks = {
    support: config.supportUrl,
    privacy: config.privacyPolicyUrl,
    terms: config.termsUrl,
    termsSale: config.termsSaleUrl,
    refund: config.refundPolicyUrl,
  };
  document.querySelectorAll("[data-config-link]").forEach((link) => {
    const url = parseHttpsUrl(publicLinks[link.dataset.configLink]);
    if (url) {
      link.href = url.href;
      link.removeAttribute("aria-disabled");
      link.removeAttribute("data-pending");
    } else {
      link.href = "#pending-integrations";
      link.setAttribute("aria-disabled", "true");
      link.dataset.pending = "true";
      link.addEventListener("click", (event) => event.preventDefault());
    }
  });

  const motionAllowed = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (motionAllowed && "IntersectionObserver" in window) {
    const revealItems = document.querySelectorAll(".section, .principle-strip, .final-cta");
    document.documentElement.classList.add("reveal-ready");
    const revealObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-revealed");
        revealObserver.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -8%", threshold: 0.08 });
    revealItems.forEach((item) => revealObserver.observe(item));
  }
})();
