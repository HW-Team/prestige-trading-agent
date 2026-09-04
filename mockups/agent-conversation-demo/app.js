/* Prestige Trading Club — conversation flow demo.
 * Mirrors the backend agent (knowledge.py + agent.py): same approved copy,
 * same intent routing, same safety rules (no guarantee claims, no paid room
 * links). Pure client-side; nothing is sent anywhere.
 */
"use strict";

const K = KNOWLEDGE;
const chat = document.getElementById("chat");
const input = document.getElementById("input");
const composer = document.getElementById("composer");
const flowState = document.getElementById("flowState");
const flowAction = document.getElementById("flowAction");
const scenarioButtons = document.querySelectorAll("[data-scenario]");

let busy = false;

/* ---------------- State machine (mirrors domain.py) ---------------- */
const STATES = {
  NEW: "ใหม่ (NEW)",
  QUALIFYING: "กำลังคัดกรอง (QUALIFYING)",
  FORM_PENDING: "รอแบบฟอร์ม (FORM_PENDING)",
  FORM_COMPLETED: "กรอกแบบฟอร์มแล้ว (FORM_COMPLETED)",
  FREE_COMMUNITY: "กลุ่มฟรี (FREE_COMMUNITY)",
  CHECKOUT_PENDING: "รอชำระเงิน (CHECKOUT_PENDING)",
  PAID_ACTIVE: "ชำระแล้ว (PAID_ACTIVE)",
  TRIAL_PENDING: "รออนุมัติทดลอง (TRIAL_PENDING)",
  TRIAL_APPROVED: "อนุมัติทดลองแล้ว (TRIAL_APPROVED)",
  HUMAN_HANDOFF: "ส่งต่อแอดมิน (HUMAN_HANDOFF)",
  UNSUBSCRIBED: "ยุติการสนทนา (UNSUBSCRIBED)",
};

let state = "NEW";

function setState(next, actionText) {
  state = next;
  flowState.textContent = STATES[next] || next;
  flowAction.textContent = actionText || "";
}

/* ---------------- Helpers ---------------- */
function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function addBubble(text, who, cls) {
  const div = document.createElement("div");
  div.className = `msg ${who}${cls ? " " + cls : ""}`;
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

function addMeta(html) {
  const div = document.createElement("div");
  div.className = "msg meta";
  div.innerHTML = html;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

function addFlag(text) {
  const div = document.createElement("div");
  div.className = "msg flag";
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

async function botSay(text, label) {
  const div = document.createElement("div");
  div.className = "msg bot";
  div.innerHTML = `<div class="typing"><span></span><span></span><span></span></div>`;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  await sleep(600 + Math.min(900, text.length * 8));
  if (label) {
    div.innerHTML = `<span class="badge">${label}</span><br>` + escapeHtml(text);
  } else {
    div.textContent = text;
  }
  chat.scrollTop = chat.scrollHeight;
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

function pick(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

/* ---------------- Safety check (mirrors apply_safety_rules) ---------------- */
const FORBIDDEN = K.forbidden_claims.map((s) => s.toLowerCase());
const ALLOWED_PREFIXES = [
  "https://lin.ee/wcilwhp",
  "https://prestigetradingclub.com/",
  "https://forms.gle/",
];

function isUnsafe(text) {
  const low = text.toLowerCase();
  if (FORBIDDEN.some((f) => low.includes(f))) return "unsafe claim";
  const urls = low.match(/https?:\/\/[^\s)\]"]+/g) || [];
  if (urls.some((u) => !ALLOWED_PREFIXES.some((p) => u.startsWith(p)))) {
    return "unsafe url";
  }
  return null;
}

/* ---------------- Intent router (mirrors agent.py _offline_route) ---------------- */
function routeIntent(text) {
  const t = text.toLowerCase();
  if (/indicator|tradingview|ทดลอง/.test(t)) {
    return { path: "indicator", reply: K.scenarios.indicator_trial.reply };
  }
  if (/course|checkout|คอร์ส|learn|สมัคร/.test(t)) {
    return { path: "course", reply: K.scenarios.course_interest.reply };
  }
  if (/มือใหม่|beginner|เริ่ม|newbie|พื้นฐาน/.test(t)) {
    return { path: "newbie", reply: K.scenarios.newbie_start.reply };
  }
  return null;
}

function findFaq(text) {
  const t = text.toLowerCase();
  for (const f of K.faqs) {
    const hay = (f.question + " " + f.variants).toLowerCase();
    const words = hay.replace(/[^\u0E00-\u0E7Fa-z0-9 ]/g, " ").split(/\s+/).filter((w) => w.length >= 4);
    const hits = words.filter((w) => t.includes(w.toLowerCase()));
    if (hits.length >= 2) return f;
  }
  return null;
}

/* ---------------- Reply generation ---------------- */
async function handleUserMessage(text) {
  const trimmed = text.trim();
  if (!trimmed || busy) return;
  busy = true;
  addBubble(trimmed, "user");

  const low = trimmed.toLowerCase();
  const unsafe = isUnsafe(trimmed);

  if (/^(หยุด|พอแล้ว|ไม่สนใจ|ขอบคุณ ไม่|bye|no thanks|stop)/i.test(trimmed)) {
    setState("UNSUBSCRIBED", "ยุติการส่งข้อความเสนอขายทันที");
    await botSay(K.response_rules.unsubscribed_reply);
    addMeta("🛑 <strong>กฎ:</strong> ยุติการส่งข้อความเสนอขายทันที");
    busy = false;
    return;
  }

  if (unsafe) {
    setState("HUMAN_HANDOFF", "ส่งต่อแอดมิน (กฎความปลอดภัย)");
    await botSay("ขออภัยครับ ข้อมูลนี้อยู่นอกเหนือขอบเขตที่ผมให้บริการได้ ขออนุญาตประสานงานให้เจ้าหน้าที่แอดมินเข้ามาดูแลโดยเร็วที่สุดครับ", "⚠️ SAFETY BLOCK");
    addFlag("บล็อกโดยกฎความปลอดภัย: " + unsafe);
    busy = false;
    return;
  }

  if (/สลิป|โอนเงินแล้ว|จ่ายแล้ว|ชำระแล้ว/.test(low)) {
    setState("PAID_ACTIVE", "แอดมินตรวจสอบสลิป → เปิดสิทธิ์");
    await botSay(K.scenarios.payment_success.confirm, "ชำระเงินสำเร็จ");
    addMeta("📋 แอดมินได้รับงาน: ตรวจสอบสลิป → ส่งลิงก์ห้องเรียน + โบนัส ภายใน 15-30 นาที");
    busy = false;
    return;
  }

  const faq = findFaq(trimmed);
  if (faq) {
    if (faq.handoff) {
      setState("HUMAN_HANDOFF", "ส่งต่อแอดมิน (FAQ 10)");
    } else {
      setState("QUALIFYING", "ตอบ FAQ → ถามต่อ 1 คำถาม");
    }
    await botSay(faq.answer, "FAQ");
    if (faq.follow_up && faq.follow_up !== "—") {
      await botSay("แล้ว " + faq.follow_up.replace(/^ถาม|สอบถาม|แนะนำ|ให้ข้อมูล|อธิบาย/, (m) => m) + " ครับ", "ถามต่อ");
    }
    if (faq.handoff) {
      addMeta("👤 <strong>ส่งต่อแอดมิน:</strong> " + faq.follow_up);
    }
    busy = false;
    return;
  }

  const route = routeIntent(trimmed);
  if (route) {
    if (route.path === "newbie") {
      setState("FORM_PENDING", "ส่งแบบฟอร์มมือใหม่ (SEND_FORM)");
      await botSay(route.reply, "มือใหม่");
      await botSay(K.scenarios.newbie_start.ask, "ถามต่อ");
      addMeta("📝 <strong>ขั้นตอนถัดไป:</strong> ส่งแบบฟอร์มศึกษาพื้นฐานฟรี → เข้ากลุ่ม LINE ฟรี");
    } else if (route.path === "course") {
      setState("CHECKOUT_PENDING", "เสนอแพ็กเกจ (SEND_CHECKOUT)");
      await botSay(route.reply, "สนใจคอร์ส");
      await botSay(K.scenarios.course_interest.ask, "ถามต่อ");
      addMeta("💳 <strong>เมื่อลูกค้าเลือก:</strong> " + K.links.checkout);
    } else {
      setState("TRIAL_PENDING", "ขอข้อมูล + รออนุมัติ (CREATE_ACCESS_REQUEST)");
      await botSay(route.reply, "สนใจ Indicator");
      await botSay("ขอข้อมูลเพื่อส่งคำขอทดลองครับ: " + K.scenarios.indicator_trial.collect, "ขอข้อมูล");
      await botSay(K.scenarios.indicator_trial.waiting_reply, "ระหว่างรอ");
      addMeta("👤 <strong>ส่งต่อแอดมิน:</strong> ตรวจสอบคำขอทดลอง Indicator");
    }
    busy = false;
    return;
  }

  /* Ambiguous */
  if (state === "QUALIFYING" || state === "NEW") {
    setState("QUALIFYING", "ถามคำถามคัดกรอง");
  }
  await botSay(K.scenarios.unclear.ask, "ไม่ชัดเจน");
  addMeta("❓ ถ้าถามแล้ว 2 ครั้งยังไม่ชัด → <strong>ส่งต่อแอดมินทันที</strong>");
  busy = false;
}

/* ---------------- Scenario playback ---------------- */
const SCENARIOS = {
  newbie: [
    { who: "user", text: "ไม่มีพื้นฐานเทรดได้ไหมครับ เริ่มต้นยังไงดี?" },
    { who: "bot", label: "มือใหม่", text: K.scenarios.newbie_start.reply },
    { who: "bot", label: "ถามต่อ", text: K.scenarios.newbie_start.ask },
    { who: "meta", text: "📝 <strong>ขั้นตอนถัดไป:</strong> แนะนำ DCTS ฉบับรวบรัด (990฿) หรือฉบับเต็ม (3,990฿) + ช่องทางศึกษาพื้นฐานฟรี" },
  ],
  course: [
    { who: "user", text: "คอร์ส DCTS คืออะไร มีกี่แบบราคาเท่าไรครับ?" },
    { who: "bot", label: "สนใจคอร์ส", text: K.scenarios.course_interest.reply },
    { who: "bot", label: "ถามต่อ", text: K.scenarios.course_interest.ask },
    { who: "meta", text: "💳 <strong>ลูกค้าเลือกแล้ว:</strong> ส่งรายละเอียด/Checkout → LINE OA: " + K.brand.support.line_oa },
  ],
  indicator: [
    { who: "user", text: "สนใจทดลอง Indicator ครับ ใช้กับ TradingView ได้ไหม?" },
    { who: "bot", label: "สนใจ Indicator", text: K.scenarios.indicator_trial.reply },
    { who: "bot", label: "ขอข้อมูล", text: "ขอข้อมูลเพื่อส่งคำขอทดลองครับ: " + K.scenarios.indicator_trial.collect },
    { who: "bot", label: "ระหว่างรอ", text: K.scenarios.indicator_trial.waiting_reply },
    { who: "meta", text: "👤 <strong>ส่งต่อแอดมิน:</strong> บันทึกข้อมูล → ตรวจสอบ → อนุมัติการทดลอง" },
  ],
  payment: [
    { who: "user", text: "โอนเงินแล้วครับ ส่งสลิปให้หน่อย" },
    { who: "bot", label: "ชำระเงินสำเร็จ", text: K.scenarios.payment_success.confirm },
    { who: "meta", text: "👤 <strong>แอดมินตรวจสอบสลิป</strong> (15 นาที) → ส่งลิงก์ห้องเรียน + โบนัส ภายใน 15-30 นาที" },
  ],
  unclear: [
    { who: "user", text: "มีเรื่องอยากถามครับ" },
    { who: "bot", label: "ไม่ชัดเจน", text: K.scenarios.unclear.ask },
    { who: "meta", text: "❓ ถ้าถามแล้ว 2 ครั้งยังไม่ชัด → <strong>ส่งต่อแอดมินทันที</strong>" },
  ],
  unsub: [
    { who: "user", text: "ไม่เอาละครับ พอแค่นี้ก่อน" },
    { who: "bot", label: "ยุติการสนทนา", text: K.response_rules.unsubscribed_reply },
    { who: "meta", text: "🛑 <strong>กฎ:</strong> ยุติการส่งข้อความเสนอขายทันที" },
  ],
};

async function playScenario(key) {
  if (busy) return;
  busy = true;
  scenarioButtons.forEach((b) => (b.disabled = true));

  if (key === "newbie") setState("FORM_PENDING", "ส่งแบบฟอร์มมือใหม่ (SEND_FORM)");
  else if (key === "course") setState("CHECKOUT_PENDING", "เสนอแพ็กเกจ (SEND_CHECKOUT)");
  else if (key === "indicator") setState("TRIAL_PENDING", "ขอข้อมูล + รออนุมัติ");
  else if (key === "payment") setState("PAID_ACTIVE", "แอดมินตรวจสอบสลิป");
  else if (key === "unclear") setState("QUALIFYING", "ถามคำถามคัดกรอง");
  else if (key === "unsub") setState("UNSUBSCRIBED", "ยุติการสนทนา");

  for (const step of SCENARIOS[key]) {
    if (step.who === "user") {
      addBubble(step.text, "user");
    } else if (step.who === "meta") {
      addMeta(step.text);
    } else {
      await botSay(step.text, step.label);
    }
    await sleep(250);
  }

  scenarioButtons.forEach((b) => (b.disabled = false));
  busy = false;
}

/* ---------------- Boot ---------------- */
function boot() {
  setState("NEW", "รอข้อความลูกค้า");
  botSay(
    K.brand.intro,
    "แนะนำตัว"
  );
  addMeta(
    "🎯 <strong>ตัวอย่าง:</strong> กดปุ่มสถานการณ์ด้านล่าง หรือพิมพ์เอง เช่น <em>\"สนใจคอร์ส 3,990 บาท\"</em>"
  );
}

composer.addEventListener("submit", (e) => {
  e.preventDefault();
  handleUserMessage(input.value);
  input.value = "";
  input.focus();
});

scenarioButtons.forEach((b) => {
  b.addEventListener("click", () => playScenario(b.dataset.scenario));
});

boot();
