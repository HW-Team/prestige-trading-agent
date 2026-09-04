"use client";

import { useEffect, useRef } from "react";
import { siteConfig } from "@/lib/site-config";

/**
 * DCTS sales page — ported 1:1 from the static page (index.html + app.js),
 * with the checkout flow moved to the server:
 *   - signup modal now collects ชื่อ / เบอร์โทร / อีเมล (funnel ข้อมูลหลังบ้าน)
 *   - POST /api/checkout creates a Stripe Checkout Session server-side
 *     (metadata carries the lead fields + UTM); falls back to the approved
 *     Payment Link when Stripe is not configured yet.
 * All interactivity is scoped to this component (no document.* queries).
 */

const APPROVED_UTM_KEYS = ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"];

function parseHttpsUrl(value: string): URL | null {
  if (typeof value !== "string" || !value.trim()) return null;
  try {
    const url = new URL(value.trim());
    if (url.protocol !== "https:" || url.username || url.password) return null;
    return url;
  } catch {
    return null;
  }
}

const APPROVED_CHECKOUT_HOSTS = new Set(["buy.stripe.com", "checkout.stripe.com"]);

function isApprovedCheckoutUrl(value: string): boolean {
  const url = parseHttpsUrl(value);
  return Boolean(url && APPROVED_CHECKOUT_HOSTS.has(url.hostname));
}

function readUtm(): Record<string, string> {
  const out: Record<string, string> = {};
  const incoming = new URLSearchParams(window.location.search);
  for (const key of APPROVED_UTM_KEYS) {
    const value = incoming.get(key);
    if (value && value.length <= 200) out[key] = value;
  }
  return out;
}

export default function SalesPage() {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;

    const body = document.body;
    const menuButton = root.querySelector<HTMLButtonElement>(".menu-toggle");
    const mobileMenu = root.querySelector<HTMLElement>("#mobile-menu");
    const hero = root.querySelector<HTMLElement>(".hero");
    const stickyCta = root.querySelector<HTMLElement>(".sticky-cta");
    const videoModal = root.querySelector<HTMLElement>("#video-modal");
    const signupModal = root.querySelector<HTMLElement>("#signup-modal");
    const consent = root.querySelector<HTMLInputElement>("#checkout-consent");
    const checkoutButton = root.querySelector<HTMLButtonElement>("#checkout-button");
    const formStatus = root.querySelector<HTMLElement>("#form-status");
    const videoStatus = root.querySelector<HTMLElement>("#video-status");
    const videoLink = root.querySelector<HTMLAnchorElement>("#video-link");
    const nameInput = root.querySelector<HTMLInputElement>("#checkout-name");
    const phoneInput = root.querySelector<HTMLInputElement>("#checkout-phone");
    const emailInput = root.querySelector<HTMLInputElement>("#checkout-email");
    let activeModal: HTMLElement | null = null;
    let lastFocused: HTMLElement | null = null;

    root.querySelectorAll<HTMLElement>("[data-fallback-image]").forEach((image) => {
      image.addEventListener("error", () => {
        image.hidden = true;
      });
    });

    function setMenu(open: boolean) {
      if (!menuButton || !mobileMenu) return;
      menuButton.setAttribute("aria-expanded", String(open));
      mobileMenu.hidden = !open;
    }
    menuButton?.addEventListener("click", () => {
      setMenu(menuButton.getAttribute("aria-expanded") !== "true");
    });
    mobileMenu?.querySelectorAll("a").forEach((link) =>
      link.addEventListener("click", () => setMenu(false)),
    );

    const focusableSelector = [
      "button:not([disabled])",
      'a[href]:not([aria-disabled="true"])',
      "input:not([disabled])",
      '[tabindex]:not([tabindex="-1"])',
    ].join(",");

    function openModal(modal: HTMLElement | null) {
      if (!modal) return;
      if (activeModal) closeModal(false);
      lastFocused = document.activeElement as HTMLElement | null;
      activeModal = modal;
      modal.hidden = false;
      body?.classList.add("modal-open");
      requestAnimationFrame(() =>
        (modal.querySelector<HTMLElement>(".modal-card"))?.focus(),
      );
    }
    function closeModal(restoreFocus = true) {
      if (!activeModal) return;
      activeModal.hidden = true;
      activeModal = null;
      body?.classList.remove("modal-open");
      if (restoreFocus && lastFocused instanceof HTMLElement) lastFocused.focus();
    }

    root.querySelectorAll<HTMLElement>("[data-open-video]").forEach((button) => {
      button.addEventListener("click", () => openModal(videoModal));
    });
    root.querySelectorAll<HTMLElement>("[data-open-signup]").forEach((button) => {
      button.addEventListener("click", () => openModal(signupModal));
    });
    root.querySelector<HTMLElement>("[data-switch-signup]")?.addEventListener("click", () => {
      closeModal(false);
      openModal(signupModal);
    });
    root.querySelectorAll<HTMLElement>("[data-close-modal]").forEach((button) => {
      button.addEventListener("click", () => closeModal());
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        if (activeModal) closeModal();
        else if (mobileMenu && !mobileMenu.hidden) setMenu(false);
        return;
      }
      if (event.key !== "Tab" || !activeModal) return;
      const focusable = [...activeModal.querySelectorAll<HTMLElement>(focusableSelector)];
      if (!focusable.length) {
        event.preventDefault();
        activeModal.querySelector<HTMLElement>(".modal-card")?.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const modalCard = activeModal.querySelector<HTMLElement>(".modal-card");
      if (
        event.shiftKey &&
        (document.activeElement === first || document.activeElement === modalCard)
      ) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });

    root.querySelectorAll<HTMLElement>("[data-accordion-group]").forEach((group, groupIndex) => {
      group.querySelectorAll<HTMLButtonElement>("article > h3 > button").forEach((button, itemIndex) => {
        const item = button.closest("article");
        const panel = item?.querySelector<HTMLElement>(".accordion-panel");
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
      const stickyButton = stickyCta.querySelector<HTMLButtonElement>("button");
      const observer = new IntersectionObserver(
        ([entry]) => {
          const visible = !entry.isIntersecting;
          stickyCta.classList.toggle("is-visible", visible);
          stickyCta.setAttribute("aria-hidden", String(!visible));
          if (stickyButton) stickyButton.tabIndex = visible ? 0 : -1;
        },
        { threshold: 0.08 },
      );
      observer.observe(hero);
    }

    const checkoutReady = isApprovedCheckoutUrl(siteConfig.checkoutUrl) || Boolean(
      process.env.NEXT_PUBLIC_CHECKOUT_URL,
    );
    function updateCheckoutState() {
      if (!checkoutButton || !consent || !formStatus) return;
      checkoutButton.disabled = !consent.checked;
      checkoutButton.dataset.configState = checkoutReady ? "ready" : "pending";
      formStatus.textContent = checkoutReady
        ? consent.checked
          ? "พร้อมส่งต่อไปยังหน้าชำระเงินของ Stripe"
          : "โปรดอ่านและยืนยันข้อมูลก่อนดำเนินการ"
        : "ระบบชำระเงินยังรอ URL ที่ได้รับอนุมัติ จึงยังไม่สามารถดำเนินการต่อได้";
    }
    consent?.addEventListener("change", updateCheckoutState);

    checkoutButton?.addEventListener("click", async () => {
      if (!consent?.checked) {
        updateCheckoutState();
        return;
      }
      const name = nameInput?.value.trim() ?? "";
      const phone = phoneInput?.value.trim() ?? "";
      const email = emailInput?.value.trim() ?? "";
      if (!name || !phone || !email) {
        if (formStatus) formStatus.textContent = "กรุณากรอกชื่อ เบอร์โทร และอีเมลให้ครบ";
        (nameInput || phoneInput || emailInput)?.focus();
        return;
      }
      if (checkoutButton) checkoutButton.disabled = true;
      if (formStatus) formStatus.textContent = "กำลังสร้างคำสั่งชำระเงิน...";
      try {
        const res = await fetch("/api/checkout", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ name, phone, email, utm: readUtm() }),
        });
        const data = (await res.json()) as { mode?: string; url?: string; message?: string };
        if (data.mode === "session" || data.mode === "payment_link") {
          if (data.url) window.location.assign(data.url);
          return;
        }
        if (formStatus) formStatus.textContent = data.message ?? "ระบบชำระเงินยังรอการตั้งค่า";
      } catch {
        if (formStatus) formStatus.textContent = "เกิดข้อผิดพลาด กรุณาลองใหม่";
      }
      if (checkoutButton) checkoutButton.disabled = false;
    });
    updateCheckoutState();

    const approvedVsl = parseHttpsUrl(siteConfig.vslUrl);
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

    const publicLinks: Record<string, string> = {
      support: siteConfig.supportUrl,
      privacy: siteConfig.privacyPolicyUrl,
      terms: siteConfig.termsUrl,
      termsSale: siteConfig.termsSaleUrl,
      refund: siteConfig.refundPolicyUrl,
    };
    root.querySelectorAll<HTMLAnchorElement>("[data-config-link]").forEach((link) => {
      const url = parseHttpsUrl(publicLinks[link.dataset.configLink ?? ""] ?? "");
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
      const revealItems = root.querySelectorAll(".section, .principle-strip, .final-cta");
      document.documentElement.classList.add("reveal-ready");
      const revealObserver = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            entry.target.classList.add("is-revealed");
            revealObserver.unobserve(entry.target);
          });
        },
        { rootMargin: "0px 0px -8%", threshold: 0.08 },
      );
      revealItems.forEach((item) => revealObserver.observe(item));
    }

    return () => {
      body?.classList.remove("modal-open");
    };
  }, []);

  return (
    <div ref={rootRef}>
      <a className="skip-link" href="#main">
        ข้ามไปยังเนื้อหา
      </a>

      <header className="site-header" id="top">
        <div className="nav-wrap shell">
          <a className="brand" href="#top">
            <span className="brand-mark" aria-hidden="true">
              <img src="/assets/dcts-emblem.svg" alt="" />
            </span>
            <span>DCTS</span>
          </a>
          <nav className="desktop-nav" aria-label="เมนูหลัก">
            <a href="#curriculum">หลักสูตร</a>
            <a href="#included">สิ่งที่ได้รับ</a>
            <a href="#evidence">หลักฐาน</a>
            <a href="#reviews">รีวิว</a>
            <a href="#faq">FAQ</a>
          </nav>
          <button className="btn btn-primary nav-cta" type="button" data-open-signup>
            สมัคร DCTS
          </button>
          <button
            className="menu-toggle"
            type="button"
            aria-expanded="false"
            aria-controls="mobile-menu"
          >
            <span className="sr-only">เปิดเมนู</span>
            <span></span>
            <span></span>
          </button>
        </div>
        <nav className="mobile-menu" id="mobile-menu" aria-label="เมนูมือถือ" hidden>
          <a href="#curriculum">หลักสูตร</a>
          <a href="#included">สิ่งที่ได้รับ</a>
          <a href="#evidence">หลักฐาน</a>
          <a href="#reviews">รีวิว</a>
          <a href="#faq">FAQ</a>
        </nav>
      </header>

      <main id="main">
        <section className="hero shell" aria-labelledby="hero-title">
          <div className="hero-copy">
            <p className="eyebrow">Daily Cash Flow Trading System</p>
            <h1 id="hero-title">เปลี่ยนการเทรดที่พึ่งอารมณ์ ให้เป็นกิจวัตรที่มี Checklist</h1>
            <p className="hero-lead">
              เรียนรู้การวางแผน บริหารความเสี่ยง และทบทวนการตัดสินใจอย่างเป็นระบบ
            </p>
            <div className="hero-actions">
              <button className="btn btn-primary" type="button" data-open-signup>
                สมัคร DCTS
              </button>
              <button className="text-action" type="button" data-open-video>
                <span className="play-mini" aria-hidden="true">
                  ▶
                </span>
                ดูคำอธิบาย 3 นาที
              </button>
            </div>
            <p className="microcopy">
              เนื้อหานี้เป็นการศึกษา ไม่ใช่คำแนะนำการลงทุน ผลลัพธ์ขึ้นอยู่กับบุคคลและสภาวะตลาด
            </p>
            <div className="hero-system-line" aria-label="องค์ประกอบหลักของระบบ">
              <span>Checklist</span>
              <span>Risk Plan</span>
              <span>Journal</span>
              <span>Daily Retest</span>
            </div>
          </div>

          <div className="hero-visual media-slot media-slot-hero">
            <img
              src="/assets/hero-learning.webp"
              srcSet="/assets/hero-learning-480.webp 480w, /assets/hero-learning-720.webp 720w, /assets/hero-learning.webp 1120w"
              sizes="(min-width: 960px) 43vw, 100vw"
              width={1120}
              height={1497}
              alt="ภาพแคมเปญเชิงสัญลักษณ์ของพื้นที่วางแผนด้วย Checklist"
              fetchPriority="high"
              data-fallback-image
            />
            <div className="media-fallback">
              <span className="slot-kicker">ASSET SLOT</span>
              <strong>ภาพการเรียนรู้หรือภาพผลิตภัณฑ์จริง</strong>
              <span>/assets/hero-learning.webp</span>
            </div>
            <div className="visual-rail" aria-hidden="true">
              SYSTEM BEFORE OUTCOME
            </div>
            <button
              className="video-trigger"
              type="button"
              data-open-video
              aria-label="เปิดวิดีโอคำอธิบาย DCTS 3 นาที"
            >
              <span aria-hidden="true">▶</span>
            </button>
            <div className="visual-caption">
              <span>DCTS METHOD FILM</span>
              <strong>03:00</strong>
            </div>
          </div>
        </section>

        <section className="principle-strip" aria-label="หลักการเรียนรู้">
          <div className="shell principle-grid">
            <p>
              <strong>Systematic</strong>
              <span>ตัดสินใจตามขั้นตอน</span>
            </p>
            <p>
              <strong>Statistical</strong>
              <span>บันทึกเพื่อทบทวน</span>
            </p>
            <p>
              <strong>Risk aware</strong>
              <span>กำหนดความเสี่ยงก่อนเริ่ม</span>
            </p>
          </div>
        </section>

        <section className="section shell problem-section" aria-labelledby="problem-title">
          <div className="section-heading narrow">
            <p className="eyebrow">เมื่อการเทรดยังไม่มีระบบ</p>
            <h2 id="problem-title">ปัญหาอาจไม่ได้อยู่ที่ความพยายาม แต่อยู่ที่ขั้นตอนก่อนตัดสินใจ</h2>
          </div>
          <div className="problem-layout">
            <article className="problem-primary">
              <span className="index">01</span>
              <h3>ไม่มีเกณฑ์เข้าที่ชัดเจน</h3>
              <p>
                การตัดสินใจตามความรู้สึกทำให้ยากต่อการแยกแยะว่าอะไรคือแผน และอะไรคือแรงกดดันเฉพาะหน้า
              </p>
            </article>
            <div className="problem-list">
              <article>
                <span className="index">02</span>
                <div>
                  <h3>ตัดสินใจถี่เกินแผน</h3>
                  <p>เวลาหน้าจอที่ยาวขึ้นอาจเพิ่มความล้าและทำให้วินัยลดลง</p>
                </div>
              </article>
              <article>
                <span className="index">03</span>
                <div>
                  <h3>ไม่บันทึกเพื่อทบทวน</h3>
                  <p>เมื่อไม่มี Journal เราจะตรวจสอบรูปแบบการตัดสินใจของตัวเองได้ยาก</p>
                </div>
              </article>
              <article>
                <span className="index">04</span>
                <div>
                  <h3>มองผลลัพธ์ก่อนความเสี่ยง</h3>
                  <p>เป้าหมายที่ใหญ่เกินแผนอาจทำให้ขนาดความเสี่ยงไม่เหมาะสม</p>
                </div>
              </article>
            </div>
          </div>
        </section>

        <section className="section model-section" id="included" aria-labelledby="model-title">
          <div className="shell model-grid">
            <div className="model-copy">
              <p className="eyebrow">วิธีทำงานแบบ DCTS</p>
              <h2 id="model-title">ห้าจังหวะที่ทำให้การตัดสินใจตรวจสอบได้</h2>
              <p>
                แทนที่จะเริ่มจากการคาดเดาผลลัพธ์ ระบบเริ่มจากเงื่อนไข ความเสี่ยง และหลักฐานที่ผู้เรียนบันทึกเอง
              </p>
              <button className="btn btn-primary" type="button" data-open-signup>
                สมัคร DCTS
              </button>
            </div>
            <ol className="process-list">
              <li>
                <span>01</span>
                <div>
                  <h3>ตรวจ Checklist</h3>
                  <p>พิจารณาเงื่อนไขก่อนทุกการตัดสินใจ</p>
                </div>
              </li>
              <li>
                <span>02</span>
                <div>
                  <h3>กำหนดช่วงวิเคราะห์</h3>
                  <p>วางกรอบเวลาเพื่อช่วยลดการเฝ้าจอโดยไม่มีแผน</p>
                </div>
              </li>
              <li>
                <span>03</span>
                <div>
                  <h3>วางกฎความเสี่ยงและทางออก</h3>
                  <p>กำหนดสิ่งที่ยอมรับได้ก่อนเข้าสู่สถานการณ์จริง</p>
                </div>
              </li>
              <li>
                <span>04</span>
                <div>
                  <h3>บันทึก Daily Retest</h3>
                  <p>เก็บเหตุผลและผลลัพธ์ไว้ทบทวนตามกระบวนการ</p>
                </div>
              </li>
              <li>
                <span>05</span>
                <div>
                  <h3>หยุดเมื่อเงื่อนไขไม่ครบ</h3>
                  <p>การไม่ตัดสินใจก็เป็นส่วนหนึ่งของระบบ</p>
                </div>
              </li>
            </ol>
          </div>
        </section>

        <section className="section shell evidence-section" id="evidence" aria-labelledby="evidence-title">
          <div className="section-heading split-heading">
            <div>
              <p className="eyebrow">หลักฐานก่อนคำกล่าวอ้าง</p>
              <h2 id="evidence-title">ดูวิธีคิด พร้อมขอบเขตข้อมูลที่ตรวจสอบได้</h2>
            </div>
            <p>
              พื้นที่นี้จะแสดงเฉพาะตัวอย่างที่ผ่านการอนุมัติ พร้อมช่วงเวลา จำนวนตัวอย่าง และวิธีคำนวณที่ชัดเจน
            </p>
          </div>
          <div className="evidence-grid">
            <div className="media-slot evidence-visual">
              <img
                src="/assets/checklist-method.webp"
                srcSet="/assets/checklist-method-640.webp 640w, /assets/checklist-method.webp 1280w"
                sizes="(min-width: 960px) 55vw, 100vw"
                width={1280}
                height={958}
                alt="ภาพแคมเปญมือกำลังจัดระเบียบ Checklist และแผนความเสี่ยง"
                loading="lazy"
                data-fallback-image
              />
              <div className="media-fallback">
                <span className="slot-kicker">ASSET SLOT</span>
                <strong>ตัวอย่าง Checklist และ Daily Retest จริง</strong>
                <span>/assets/checklist-method.webp</span>
              </div>
            </div>
            <article className="evidence-card">
              <div className="evidence-icon" aria-hidden="true">
                Σ
              </div>
              <p className="slot-kicker">STATISTICAL EVIDENCE SLOT</p>
              <h3>หลักฐานเชิงสถิติที่ผ่านการตรวจสอบ</h3>
              <ul>
                <li>ระบุช่วงวันที่ของข้อมูล</li>
                <li>ระบุจำนวนตัวอย่างและเกณฑ์คัดเลือก</li>
                <li>อธิบายวิธีคำนวณ ค่าธรรมเนียม และข้อจำกัด</li>
              </ul>
              <p className="evidence-note">ยังไม่แสดงตัวเลขจนกว่าหลักฐานและถ้อยคำจะได้รับอนุมัติ</p>
            </article>
          </div>
          <p className="risk-inline">
            ผลการดำเนินงานในอดีตไม่รับรองผลในอนาคต การซื้อขายมีความเสี่ยงต่อการสูญเสียเงินทุน
          </p>
        </section>

        <section className="section curriculum-section" id="curriculum" aria-labelledby="curriculum-title">
          <div className="shell curriculum-layout">
            <div className="curriculum-intro">
              <p className="eyebrow">โครงสร้างการเรียน</p>
              <h2 id="curriculum-title">ห้าโมดูล จากการเตรียมแผนถึงการทบทวน</h2>
              <p>เรียนเป็นลำดับ พร้อมแบบฝึกหัดและเครื่องมือสำหรับสร้างกิจวัตรของตัวเอง</p>
              <div className="media-slot lms-slot">
                <div className="media-fallback">
                  <span className="slot-kicker">LMS SCREENSHOT SLOT</span>
                  <strong>ภาพหน้าจอระบบเรียนจริง</strong>
                  <span>รอไฟล์ที่ปกปิดข้อมูลผู้ใช้แล้ว</span>
                </div>
              </div>
            </div>
            <div className="module-accordion" data-accordion-group>
              <article className="module is-open">
                <h3>
                  <button type="button" aria-expanded="true">
                    <span>01</span>วางกรอบคิดและเป้าหมาย
                    <svg viewBox="0 0 20 20" aria-hidden="true">
                      <path d="M5 7.5 10 12.5 15 7.5" />
                    </svg>
                  </button>
                </h3>
                <div className="accordion-panel">
                  <p>ทำความเข้าใจบทบาทของระบบ วินัย และขอบเขตความเสี่ยงที่เหมาะกับผู้เรียน</p>
                </div>
              </article>
              <article className="module">
                <h3>
                  <button type="button" aria-expanded="false">
                    <span>02</span>อ่านเงื่อนไขด้วย Checklist
                    <svg viewBox="0 0 20 20" aria-hidden="true">
                      <path d="M5 7.5 10 12.5 15 7.5" />
                    </svg>
                  </button>
                </h3>
                <div className="accordion-panel" hidden>
                  <p>ฝึกแยกเงื่อนไขที่ครบ ไม่ครบ และสถานการณ์ที่ควรรอ โดยไม่พึ่งการคาดเดา</p>
                </div>
              </article>
              <article className="module">
                <h3>
                  <button type="button" aria-expanded="false">
                    <span>03</span>กำหนดความเสี่ยงและทางออก
                    <svg viewBox="0 0 20 20" aria-hidden="true">
                      <path d="M5 7.5 10 12.5 15 7.5" />
                    </svg>
                  </button>
                </h3>
                <div className="accordion-panel" hidden>
                  <p>วางแผนขนาดความเสี่ยง จุดยุติ และแนวทางรับมือก่อนตัดสินใจ</p>
                </div>
              </article>
              <article className="module">
                <h3>
                  <button type="button" aria-expanded="false">
                    <span>04</span>บันทึก Trade Journal
                    <svg viewBox="0 0 20 20" aria-hidden="true">
                      <path d="M5 7.5 10 12.5 15 7.5" />
                    </svg>
                  </button>
                </h3>
                <div className="accordion-panel" hidden>
                  <p>เก็บเหตุผล ภาพประกอบ และผลการทำตามแผน เพื่อใช้เป็นข้อมูลทบทวน</p>
                </div>
              </article>
              <article className="module">
                <h3>
                  <button type="button" aria-expanded="false">
                    <span>05</span>ทำ Daily Retest
                    <svg viewBox="0 0 20 20" aria-hidden="true">
                      <path d="M5 7.5 10 12.5 15 7.5" />
                    </svg>
                  </button>
                </h3>
                <div className="accordion-panel" hidden>
                  <p>ทบทวนตัวอย่างตามเกณฑ์เดียวกัน เพื่อมองเห็นความสม่ำเสมอของกระบวนการ</p>
                </div>
              </article>
            </div>
          </div>
        </section>

        <section className="section shell coach-section" aria-labelledby="coach-title">
          <div className="media-slot portrait-slot">
            <div className="media-fallback">
              <span className="slot-kicker">REAL PORTRAIT SLOT</span>
              <strong>ภาพ Coach Golf ตัวจริง</strong>
              <span>รอภาพและประวัติที่ได้รับอนุมัติ</span>
            </div>
          </div>
          <div className="coach-copy">
            <p className="eyebrow">โค้ชและระบบสนับสนุน</p>
            <h2 id="coach-title">เรียนกับผู้สอนที่อธิบายกระบวนการ ไม่ตัดสินใจแทนผู้เรียน</h2>
            <p>
              พื้นที่ประวัติของ Coach Golf จะแสดงเฉพาะข้อมูลที่ตรวจสอบและอนุมัติแล้ว พร้อมขอบเขตการดูแลที่ชัดเจน
            </p>
            <dl className="support-spec">
              <div>
                <dt>ช่องทางสนับสนุน</dt>
                <dd>รอยืนยันช่องทางอย่างเป็นทางการ</dd>
              </div>
              <div>
                <dt>เวลาตอบกลับ</dt>
                <dd>รอยืนยันวัน เวลา และ SLA</dd>
              </div>
              <div>
                <dt>ขอบเขต Daily Retest</dt>
                <dd>ทบทวนการใช้ Checklist และ Journal ไม่ใช่บริการบอกคำสั่งซื้อขาย</dd>
              </div>
            </dl>
          </div>
        </section>

        <section className="section reviews-section" id="reviews" aria-labelledby="reviews-title">
          <div className="shell">
            <div className="section-heading split-heading">
              <div>
                <p className="eyebrow">ประสบการณ์จากผู้เรียน</p>
                <h2 id="reviews-title">ใช้เสียงจริง เมื่อได้รับความยินยอมแล้วเท่านั้น</h2>
              </div>
              <p>ไม่มีคำรับรองสมมติ และไม่มีผลลัพธ์ด้านรายได้ที่ยังไม่ได้ตรวจสอบ</p>
            </div>
            <div className="testimonial-slots">
              <article className="testimonial-slot">
                <span className="slot-kicker">STUDENT VIDEO TESTIMONIAL SLOT 01</span>
                <strong>วิดีโอผู้เรียนจริง</strong>
                <p>รอไฟล์ ชื่อที่อนุญาตให้แสดง และหนังสือยินยอม</p>
              </article>
              <article className="testimonial-slot">
                <span className="slot-kicker">STUDENT VIDEO TESTIMONIAL SLOT 02</span>
                <strong>วิดีโอผู้เรียนจริง</strong>
                <p>รอไฟล์ ชื่อที่อนุญาตให้แสดง และหนังสือยินยอม</p>
              </article>
              <article className="testimonial-slot">
                <span className="slot-kicker">STUDENT VIDEO TESTIMONIAL SLOT 03</span>
                <strong>วิดีโอผู้เรียนจริง</strong>
                <p>รอไฟล์ ชื่อที่อนุญาตให้แสดง และหนังสือยินยอม</p>
              </article>
            </div>
            <p className="microcopy centered">
              ประสบการณ์ของผู้เรียนแต่ละรายแตกต่างกัน และไม่ใช่หลักประกันผลลัพธ์ของผู้เรียนรายอื่น
            </p>
          </div>
        </section>

        <section className="section offer-section" aria-labelledby="offer-title">
          <div className="shell offer-grid">
            <div className="offer-copy">
              <p className="eyebrow">สิ่งที่รวมใน DCTS</p>
              <h2 id="offer-title">ระบบการเรียนที่พาคุณลงมือทำทีละขั้น</h2>
              <p>
                รายละเอียดระยะเวลาเข้าถึง ตารางสอนสด และเงื่อนไขบริการจะยืนยันก่อนเปิดรับสมัครจริง
              </p>
            </div>
            <div className="offer-card">
              <ul className="check-list">
                <li>บทเรียน 5 โมดูล</li>
                <li>คลาสสอนสดและวิดีโอย้อนหลัง ตามตารางที่ประกาศ</li>
                <li>DCTS Master Checklist</li>
                <li>Trade Journal และ Stats Workbook</li>
                <li>คลังกรณีศึกษาที่ผ่านการอนุมัติ</li>
                <li>ชุมชนสนับสนุนตามขอบเขตบริการ</li>
              </ul>
              <div className="price-block">
                <span>ราคาที่เสนอในเอกสารร่าง</span>
                <strong>3,990 THB</strong>
                <em>รอยืนยันราคาและเงื่อนไข</em>
              </div>
              <button className="btn btn-primary btn-full" type="button" data-open-signup>
                สมัคร DCTS
              </button>
              <p className="secure-note">
                การชำระเงินยังไม่เปิดใช้งาน จนกว่าจะมี URL ของ Stripe และเงื่อนไขที่ได้รับอนุมัติ
              </p>
            </div>
          </div>
        </section>

        <section className="section support-promise shell" aria-labelledby="support-title">
          <div>
            <p className="eyebrow">คำมั่นด้านการสนับสนุน</p>
            <h2 id="support-title">ทบทวนวิธีใช้ ไม่รับรองผลการเทรด</h2>
          </div>
          <div>
            <p>
              หากทำตามบทเรียนและ Checklist ครบตามเงื่อนไข แต่ยังไม่เข้าใจกระบวนการ ทีมจะนัดทบทวนแนวทางการใช้งานให้ตามขอบเขตที่ระบุ
            </p>
            <p className="policy-placeholder">
              รอยืนยันเกณฑ์สิทธิ์ หลักฐาน Journal ช่วงเวลายื่นคำขอ รูปแบบการช่วยเหลือ และนโยบายคืนเงินหรือยกเลิก
            </p>
          </div>
        </section>

        <section className="section faq-section" id="faq" aria-labelledby="faq-title">
          <div className="shell faq-layout">
            <div className="faq-intro">
              <p className="eyebrow">คำถามที่พบบ่อย</p>
              <h2 id="faq-title">อ่านเงื่อนไขให้ครบ ก่อนตัดสินใจ</h2>
              <p>คำตอบบางส่วนเป็นพื้นที่รอการอนุมัติสำหรับหน้าจริง</p>
            </div>
            <div className="faq-list" data-accordion-group>
              <article className="faq-item">
                <h3>
                  <button type="button" aria-expanded="false">
                    เหมาะกับผู้มีประสบการณ์ระดับใด?<span aria-hidden="true">+</span>
                  </button>
                </h3>
                <div className="accordion-panel" hidden>
                  <p>
                    ออกแบบสำหรับผู้ที่ต้องการสร้างขั้นตอนการตัดสินใจและการทบทวนอย่างมีระบบ เกณฑ์ความรู้พื้นฐานจะระบุให้ชัดเจนก่อนเปิดรับสมัคร
                  </p>
                </div>
              </article>
              <article className="faq-item">
                <h3>
                  <button type="button" aria-expanded="false">
                    ต้องใช้แพลตฟอร์มใดบ้าง?<span aria-hidden="true">+</span>
                  </button>
                </h3>
                <div className="accordion-panel" hidden>
                  <p>รายการเครื่องมือ บัญชีทดลอง และข้อกำหนดทางเทคนิคอยู่ระหว่างยืนยัน ผู้เรียนควรตรวจสอบก่อนชำระเงิน</p>
                </div>
              </article>
              <article className="faq-item">
                <h3>
                  <button type="button" aria-expanded="false">
                    มีคลาสสดและวิดีโอย้อนหลังหรือไม่?<span aria-hidden="true">+</span>
                  </button>
                </h3>
                <div className="accordion-panel" hidden>
                  <p>
                    มีแผนสำหรับคลาสสดและวิดีโอย้อนหลัง โดยตาราง ระยะเวลาเข้าถึง และข้อจำกัดจะระบุในเงื่อนไขการขายฉบับอนุมัติ
                  </p>
                </div>
              </article>
              <article className="faq-item">
                <h3>
                  <button type="button" aria-expanded="false">
                    Daily Retest ครอบคลุมอะไร?<span aria-hidden="true">+</span>
                  </button>
                </h3>
                <div className="accordion-panel" hidden>
                  <p>
                    เน้นการทบทวนการใช้ Checklist และ Journal ตามกรอบการศึกษา ไม่ใช่คำแนะนำเฉพาะบุคคลหรือบริการบอกคำสั่งซื้อขาย
                  </p>
                </div>
              </article>
              <article className="faq-item">
                <h3>
                  <button type="button" aria-expanded="false">
                    ชำระเงินและขอใบเสร็จอย่างไร?<span aria-hidden="true">+</span>
                  </button>
                </h3>
                <div className="accordion-panel" hidden>
                  <p>
                    การชำระเงินจริงจะส่งต่อไปยังผู้ให้บริการที่ได้รับอนุมัติ รายละเอียดใบเสร็จและนิติบุคคลอยู่ระหว่างยืนยัน
                  </p>
                </div>
              </article>
              <article className="faq-item">
                <h3>
                  <button type="button" aria-expanded="false">
                    ยกเลิกหรือขอคืนเงินได้หรือไม่?<span aria-hidden="true">+</span>
                  </button>
                </h3>
                <div className="accordion-panel" hidden>
                  <p>รอนโยบายการยกเลิกและคืนเงินฉบับอนุมัติ โปรดอ่านเงื่อนไขก่อนชำระเงินทุกครั้ง</p>
                </div>
              </article>
              <article className="faq-item">
                <h3>
                  <button type="button" aria-expanded="false">
                    การเรียนช่วยลดความเสี่ยงได้อย่างไร?<span aria-hidden="true">+</span>
                  </button>
                </h3>
                <div className="accordion-panel" hidden>
                  <p>หลักสูตรสอนให้กำหนดและทบทวนความเสี่ยงอย่างมีขั้นตอน แต่ไม่สามารถกำจัดความเสี่ยงหรือรับรองผลลัพธ์จากตลาดได้</p>
                </div>
              </article>
            </div>
          </div>
        </section>

        <section className="final-cta" aria-labelledby="final-title">
          <div className="shell final-cta-inner">
            <p className="eyebrow">เริ่มจากกระบวนการที่ตรวจสอบได้</p>
            <h2 id="final-title">สร้าง Checklist บันทึกการตัดสินใจ และทบทวนอย่างมีวินัย</h2>
            <button className="btn btn-accent" type="button" data-open-signup>
              สมัคร DCTS
            </button>
            <a href="#faq" className="support-link">
              ยังมีคำถาม ดู FAQ ก่อนตัดสินใจ
            </a>
            <a href="#pending-integrations" className="support-link" data-config-link="support" data-pending="true" aria-disabled="true">
              ช่องทางช่วยเหลือ (รออนุมัติ)
            </a>
          </div>
        </section>
      </main>

      <footer className="site-footer">
        <div className="shell footer-grid">
          <div>
            <a className="brand footer-brand" href="#top">
              <span className="brand-mark" aria-hidden="true">
                <img src="/assets/dcts-emblem.svg" alt="" />
              </span>
              <span>DCTS</span>
            </a>
            <p>หลักสูตรการศึกษาเพื่อพัฒนากระบวนการตัดสินใจและการบริหารความเสี่ยง</p>
          </div>
          <div>
            <h2>นโยบาย</h2>
            <a href="#pending-integrations" data-config-link="privacy" data-pending="true" aria-disabled="true">
              Privacy Policy (รออนุมัติ)
            </a>
            <a href="#pending-integrations" data-config-link="terms" data-pending="true" aria-disabled="true">
              Terms of Use (รออนุมัติ)
            </a>
            <a href="#pending-integrations" data-config-link="termsSale" data-pending="true" aria-disabled="true">
              Terms of Sale (รออนุมัติ)
            </a>
            <a href="#pending-integrations" data-config-link="refund" data-pending="true" aria-disabled="true">
              นโยบายยกเลิกและคืนเงิน (รออนุมัติ)
            </a>
          </div>
          <div id="pending-integrations">
            <h2>ข้อมูลผู้ให้บริการ</h2>
            <p>รอชื่อนิติบุคคล ที่อยู่ เลขทะเบียน และช่องทางติดต่ออย่างเป็นทางการ</p>
          </div>
        </div>
        <div className="shell risk-disclaimer">
          <strong>คำเตือนความเสี่ยง</strong>
          <p>
            การลงทุนมีความเสี่ยง การซื้อขายผลิตภัณฑ์ทางการเงินอาจทำให้สูญเสียเงินลงทุน เนื้อหานี้มีวัตถุประสงค์เพื่อการศึกษาเท่านั้น
            ไม่ใช่คำแนะนำด้านการลงทุน กฎหมาย ภาษี หรือการเงิน และไม่รับประกันผลกำไรหรือผลตอบแทน โปรดประเมินความเหมาะสมและปรึกษาผู้เชี่ยวชาญที่ได้รับอนุญาตเมื่อจำเป็น
            ผลการดำเนินงานในอดีตไม่รับรองผลในอนาคต
          </p>
        </div>
      </footer>

      <div className="sticky-cta" aria-hidden="true">
        <button className="btn btn-primary btn-full" type="button" data-open-signup tabIndex={-1}>
          สมัคร DCTS
        </button>
      </div>

      <div className="modal" id="video-modal" role="dialog" aria-modal="true" aria-labelledby="video-modal-title" hidden>
        <div className="modal-backdrop" data-close-modal></div>
        <div className="modal-card video-modal-card" tabIndex={-1}>
          <button className="modal-close" type="button" data-close-modal aria-label="ปิดหน้าต่าง">
            ×
          </button>
          <p className="eyebrow">วิดีโอคำอธิบาย DCTS</p>
          <h2 id="video-modal-title">ทำความเข้าใจระบบใน 3 นาที</h2>
          <div className="video-placeholder">
            <span className="play-large" aria-hidden="true">
              ▶
            </span>
            <strong>วิดีโอคำอธิบาย</strong>
            <span id="video-status" role="status">
              รอวิดีโอและ URL ที่ได้รับอนุมัติ
            </span>
          </div>
          <p>วิดีโอจริงจะอธิบายว่า DCTS คืออะไร เหมาะกับใคร และผู้เรียนจะฝึกกระบวนการใดบ้าง</p>
          <a className="btn btn-secondary btn-full" id="video-link" href="#pending-integrations" target="_blank" rel="noopener noreferrer" hidden>
            เปิดวิดีโอที่ได้รับอนุมัติ
          </a>
          <button className="btn btn-primary btn-full" type="button" data-switch-signup>
            สมัคร DCTS
          </button>
        </div>
      </div>

      <div className="modal" id="signup-modal" role="dialog" aria-modal="true" aria-labelledby="signup-modal-title" hidden>
        <div className="modal-backdrop" data-close-modal></div>
        <div className="modal-card signup-modal-card" tabIndex={-1}>
          <button className="modal-close" type="button" data-close-modal aria-label="ปิดหน้าต่าง">
            ×
          </button>
          <p className="eyebrow">ขั้นตอนสมัคร</p>
          <h2 id="signup-modal-title">ตรวจสอบข้อมูลก่อนเข้าสู่การชำระเงิน</h2>
          <div className="checkout-summary">
            <div>
              <span>รายการ</span>
              <strong>DCTS</strong>
            </div>
            <div>
              <span>ราคาจากเอกสารร่าง</span>
              <strong>3,990 THB</strong>
            </div>
            <em>รอยืนยันราคาและเงื่อนไข</em>
          </div>
          <div className="checkout-fields">
            <label>
              <span>ชื่อ-นามสกุล</span>
              <input id="checkout-name" type="text" autoComplete="name" maxLength={255} required />
            </label>
            <label>
              <span>เบอร์โทร</span>
              <input id="checkout-phone" type="tel" autoComplete="tel" maxLength={40} required />
            </label>
            <label>
              <span>อีเมล</span>
              <input id="checkout-email" type="email" autoComplete="email" maxLength={255} required />
            </label>
          </div>
          <ol className="checkout-steps">
            <li>
              <span>1</span>ตรวจสอบราคา เงื่อนไข และนโยบาย
            </li>
            <li>
              <span>2</span>ส่งต่อไปยังหน้าชำระเงินที่ปลอดภัย
            </li>
            <li>
              <span>3</span>เปิดสิทธิ์เรียนหลังระบบยืนยันการชำระเงินจริง
            </li>
          </ol>
          <label className="consent-row">
            <input type="checkbox" id="checkout-consent" />
            <span>ฉันอ่านคำเตือนความเสี่ยง และเข้าใจว่าราคา 3,990 THB กับเงื่อนไขยังรอการยืนยัน</span>
          </label>
          <button className="btn btn-primary btn-full" type="button" id="checkout-button" data-config-state="pending" disabled>
            สมัคร DCTS
          </button>
          <p className="form-status" id="form-status" role="status" aria-live="polite"></p>
          <p className="secure-note">
            หน้านี้ไม่เก็บข้อมูลการชำระเงิน การยืนยันการชำระและการเปิดสิทธิ์เกิดขึ้นในระบบฝั่งเซิร์ฟเวอร์เท่านั้น
          </p>
        </div>
      </div>
    </div>
  );
}
