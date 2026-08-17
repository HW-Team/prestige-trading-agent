const RESPONSE_SPREADSHEET_ID = '1Hi5KpWDCy-4UCqCk5rkgWWfQdBPdBOvPjaV_hoJBqNA';
const INSTRUCTION_SHEET = '11_สร้าง_Google_Form';

function createPrestigeKnowledgeForm() {
  const spreadsheet = SpreadsheetApp.openById(RESPONSE_SPREADSHEET_ID);
  const instructionSheet = spreadsheet.getSheetByName(INSTRUCTION_SHEET);
  if (!instructionSheet) {
    throw new Error('ไม่พบแท็บ ' + INSTRUCTION_SHEET);
  }
  if (instructionSheet.getRange('B2').getValue()) {
    throw new Error('สร้างฟอร์มแล้ว กรุณาเปิดลิงก์ใน B2 หากต้องการสร้างใหม่ ให้ล้าง B2:B3 ก่อน');
  }

  const form = FormApp.create('Prestige Trading Club — แบบฟอร์มข้อมูลสำหรับ AI Agent');
  form
    .setDescription(
      'แบบฟอร์มนี้ใช้รวบรวมข้อมูลที่ได้รับอนุมัติสำหรับตั้งค่า AI Agent เช่น ข้อมูลแบรนด์ สินค้า Conversation Flow, FAQ, Upsell, Downsell และกฎการส่งต่อทีม\n\nห้ามกรอก Password, API key, Secret, Token หรือข้อมูลบัตรลงในแบบฟอร์มนี้'
    )
    .setConfirmationMessage('รับข้อมูลเรียบร้อยแล้ว ขอบคุณครับ ทีมสามารถกลับมาแก้ไข Form หรือแจ้ง CZ เพื่อส่งข้อมูลให้ Rook ตรวจสอบได้')
    .setCollectEmail(true)
    .setProgressBar(true)
    .setShowLinkToRespondAgain(true)
    .setDestination(FormApp.DestinationType.SPREADSHEET, RESPONSE_SPREADSHEET_ID)
    .setAcceptingResponses(true);

  addPage(form, '1. ข้อมูลผู้กรอกและการอนุมัติ', 'ใช้ระบุเจ้าของข้อมูลและผู้ที่มีสิทธิ์อนุมัติ');
  addText(form, 'ชื่อ–นามสกุลผู้กรอก', true);
  addText(form, 'ตำแหน่ง/ทีม', true);
  addText(form, 'ชื่อผู้อนุมัติข้อมูล', true);
  addChoice(form, 'สถานะข้อมูลชุดนี้', ['ร่าง', 'รอตรวจ', 'อนุมัติแล้ว'], true);
  addParagraph(form, 'หมายเหตุเกี่ยวกับข้อมูลชุดนี้', false);

  addPage(form, '2. ข้อมูลแบรนด์และวิธีพูด', 'กำหนดตัวตน น้ำเสียง และข้อจำกัดของ Agent');
  addText(form, 'ชื่อแบรนด์ที่ Agent ต้องใช้', true);
  addParagraph(form, 'Agent ควรแนะนำตัวว่าอย่างไร', true, 'ตัวอย่าง: ผมเป็นผู้ช่วย AI ของ Prestige Trading Club ครับ');
  addChoice(form, 'ภาษาหลัก', ['ไทย', 'อังกฤษ', 'ตอบตามภาษาของลูกค้า'], true);
  addParagraph(form, 'น้ำเสียงและบุคลิกของ Agent', true, 'เช่น เป็นมิตร มืออาชีพ กระชับ ไม่ขายกดดัน');
  addParagraph(form, 'จุดเด่นของแบรนด์ที่ยืนยันได้ 3–5 ข้อ', true);
  addParagraph(form, 'คำหรือคำกล่าวอ้างที่ห้ามใช้', true, 'เช่น การันตีกำไร ไม่มีความเสี่ยง รวยเร็ว');
  addParagraph(form, 'Disclaimer ที่ได้รับอนุมัติ', true);
  addText(form, 'ช่องทางติดต่อ Support', true);
  addText(form, 'วันและเวลาทำการของทีม', true);

  addPage(form, '3. กลุ่มลูกค้าและคำถามคัดกรอง', 'ระบุ Persona และวิธีแยก Beginner, Course, Indicator และลูกค้าปัจจุบัน');
  addParagraph(form, 'กลุ่มลูกค้าหลักทั้งหมดมีใครบ้าง', true);
  addParagraph(form, 'สัญญาณหรือคำพูดที่บอกว่าเป็น “มือใหม่”', true);
  addParagraph(form, 'สัญญาณหรือคำพูดที่บอกว่าสนใจ “คอร์ส”', true);
  addParagraph(form, 'สัญญาณหรือคำพูดที่บอกว่าสนใจ “Indicator”', true);
  addParagraph(form, 'สัญญาณว่าเป็นลูกค้าปัจจุบันที่ต้องการ Support', true);
  addParagraph(form, 'คำถามคัดกรองที่ Agent ต้องถาม และลำดับคำถาม', true, 'ขอให้ถามทีละคำถาม');
  addParagraph(form, 'ข้อมูลใดที่ต้องเก็บจาก Lead ทุกคน', true);

  addPage(form, '4. สินค้า แพ็กเกจ และราคา', 'กรอกเฉพาะราคาและเงื่อนไขที่ได้รับอนุมัติแล้ว');
  addPackageQuestions(form, 'แพ็กเกจที่ 1');
  addPackageQuestions(form, 'แพ็กเกจที่ 2');
  addPackageQuestions(form, 'แพ็กเกจที่ 3');
  addPackageQuestions(form, 'แพ็กเกจที่ 4');
  addPackageQuestions(form, 'แพ็กเกจที่ 5');
  addParagraph(form, 'นโยบายคืนเงิน ยกเลิก และเปลี่ยนแพ็กเกจ', true);
  addParagraph(form, 'สิ่งที่ระบบต้องทำหลัง Stripe ยืนยันการชำระเงิน', true);

  addPage(form, '5. Beginner Conversation Flow', 'Flow สำหรับผู้เริ่มต้นและกลุ่ม LINE ฟรี');
  addParagraph(form, 'ข้อความ Trigger/Intent ของ Beginner', true);
  addParagraph(form, 'ข้อความตอบแรกที่อนุมัติ', true);
  addParagraph(form, 'คำถามที่ Agent ต้องถามต่อ', true);
  addText(form, 'URL แบบฟอร์ม Beginner', true);
  addParagraph(form, 'เงื่อนไขก่อนส่งลิงก์ LINE ฟรี', true);
  addParagraph(form, 'ข้อความหลังกรอกฟอร์มสำเร็จ', true);
  addParagraph(form, 'กรณีที่ต้องส่งต่อมนุษย์', true);

  addPage(form, '6. Course Conversation Flow', 'Flow สำหรับคอร์ส DCTS ตั้งแต่สนใจจนเข้า LMS');
  addParagraph(form, 'ข้อความ Trigger/Intent ของผู้สนใจคอร์ส', true);
  addParagraph(form, 'รายละเอียดคอร์สที่ Agent สามารถตอบได้', true);
  addParagraph(form, 'ข้อความตอบและคำถามถัดไปที่อนุมัติ', true);
  addText(form, 'Checkout URL ของคอร์ส', true);
  addParagraph(form, 'ข้อความหลังชำระเงินสำเร็จ', true);
  addParagraph(form, 'ขั้นตอน Enroll เข้า LMS', true);
  addParagraph(form, 'กรณีชำระเงินแล้วแต่ไม่ได้สิทธิ์', true);
  addParagraph(form, 'กรณีที่ต้องส่งต่อมนุษย์', true);

  addPage(form, '7. Indicator และ Trial Conversation Flow', 'Flow ทดลอง Indicator แบบไม่ใช้บัตรและต้องมี Approval');
  addParagraph(form, 'ชื่อ Indicator และคำอธิบายที่อนุมัติ', true);
  addParagraph(form, 'ตลาด/Timeframe/TradingView Plan ที่รองรับ', true);
  addParagraph(form, 'ข้อความ Trigger/Intent ของผู้สนใจ Indicator', true);
  addParagraph(form, 'เงื่อนไข Trial และระยะเวลาทดลอง', true);
  addText(form, 'URL แบบฟอร์มทดลอง Indicator', true);
  addParagraph(form, 'ข้อมูลที่ต้องเก็บก่อนสร้าง Approval Request', true);
  addParagraph(form, 'ใครเป็นผู้อนุมัติ และ SLA เท่าไร', true);
  addParagraph(form, 'ข้อความแจ้งลูกค้าระหว่างรออนุมัติ', true);
  addParagraph(form, 'ข้อจำกัดหรือสิ่งที่ Agent ห้ามกล่าวอ้าง', true);

  addPage(form, '8. Upsell', 'กำหนดกฎเสนอแพ็กเกจที่สูงขึ้นโดยไม่กดดันลูกค้า');
  addOfferQuestions(form, 'Upsell ที่ 1', 'Upsell');
  addOfferQuestions(form, 'Upsell ที่ 2', 'Upsell');
  addOfferQuestions(form, 'Upsell ที่ 3', 'Upsell');
  addParagraph(form, 'สถานการณ์ที่ห้าม Upsell', true);
  addText(form, 'Cooldown ก่อนเสนอซ้ำ', true);
  addText(form, 'จำนวนครั้งสูงสุดที่ Agent เสนอได้', true);

  addPage(form, '9. Downsell', 'กำหนดข้อเสนอที่ราคาหรือ Commitment ต่ำลงเมื่อลูกค้ายังไม่พร้อม');
  addOfferQuestions(form, 'Downsell ที่ 1', 'Downsell');
  addOfferQuestions(form, 'Downsell ที่ 2', 'Downsell');
  addOfferQuestions(form, 'Downsell ที่ 3', 'Downsell');
  addParagraph(form, 'สถานการณ์ที่ห้าม Downsell', true);
  addParagraph(form, 'Agent ต้องทำอะไรเมื่อลูกค้าปฏิเสธชัดเจน', true);

  addPage(form, '10. FAQ', 'กรอกคำถามหลายรูปแบบ คำตอบที่อนุมัติ และ Next Action');
  for (let i = 1; i <= 10; i++) {
    addFAQQuestions(form, i);
  }

  addPage(form, '11. Handoff และการส่งต่อมนุษย์', 'กำหนด Trigger ผู้รับผิดชอบ SLA และข้อมูลสรุป');
  addParagraph(form, 'เหตุผลทั้งหมดที่ต้องส่งต่อมนุษย์', true);
  addParagraph(form, 'Keyword หรือ Trigger ที่ต้องส่งต่อทันที', true);
  addParagraph(form, 'ข้อมูลที่ Agent ต้องเก็บก่อนส่งต่อ', true);
  addParagraph(form, 'ข้อความแจ้งลูกค้าระหว่างส่งต่อ', true);
  addParagraph(form, 'ทีม/บุคคลผู้รับผิดชอบแต่ละประเภท', true);
  addParagraph(form, 'SLA ของแต่ละประเภท', true);
  addParagraph(form, 'ช่องทางที่ใช้แจ้งทีมภายใน', true);

  addPage(form, '12. กฎการตอบและ Compliance', 'กฎส่วนนี้ควรถูกบังคับด้วยระบบ ไม่ปล่อยให้โมเดลตัดสินใจเอง');
  addParagraph(form, 'รูปแบบคำตอบที่ต้องการ', true, 'เช่น 1–4 ประโยค ถามทีละ 1 คำถาม และมี CTA เดียว');
  addParagraph(form, 'สิ่งที่ Agent ต้องทำเมื่อไม่รู้คำตอบ', true);
  addParagraph(form, 'ข้อความเกี่ยวกับความเสี่ยง/การลงทุนที่อนุญาต', true);
  addParagraph(form, 'ข้อความเกี่ยวกับความเสี่ยง/การลงทุนที่ห้าม', true);
  addParagraph(form, 'กฎสำหรับลิงก์ LINE ห้องฟรี', true);
  addParagraph(form, 'กฎสำหรับลิงก์ LINE ห้องเสียเงิน', true);
  addParagraph(form, 'กฎเมื่อผู้ใช้บอกว่าไม่สนใจหรือขอหยุดข้อความ', true);
  addParagraph(form, 'กฎการใช้ Emoji และระดับความเป็นทางการ', false);

  addPage(form, '13. ลิงก์และข้อมูลตั้งค่าที่เปิดเผยได้', 'ห้ามกรอก Secret, Password, Token หรือ API key');
  addText(form, 'Beginner Form URL', true);
  addText(form, 'Course Checkout URL', true);
  addText(form, 'Indicator Trial Form URL', true);
  addText(form, 'Free LINE Invite URL', true);
  addText(form, 'LMS Public URL', true);
  addText(form, 'Privacy Policy URL', true);
  addText(form, 'Terms URL', true);
  addText(form, 'Support Contact', true);
  addText(form, 'Support Hours', true);
  addText(form, 'ชื่อโมเดล AI ที่ต้องการใช้ (ห้ามใส่ API key)', false);

  addPage(form, '14. ตัวอย่างบทสนทนาและการอนุมัติสุดท้าย', 'ใช้ตัวอย่างจริงเพื่อให้ Agent เรียนรู้วิธีพูดของแบรนด์');
  addParagraph(form, 'ตัวอย่างบทสนทนาที่ดี', true);
  addParagraph(form, 'ตัวอย่างบทสนทนาที่ไม่ดีและเหตุผล', true);
  addParagraph(form, 'คำถามหรือข้อมูลที่ยังขาด', false);
  addCheckbox(form, 'การยืนยันก่อนส่ง', [
    'ตรวจสอบราคาและแพ็กเกจแล้ว',
    'ตรวจสอบ URL แล้ว',
    'ตรวจสอบ Compliance แล้ว',
    'ไม่มี Password, API key, Secret หรือ Token ในคำตอบ',
    'ผู้มีอำนาจอนุมัติข้อมูลชุดนี้แล้ว'
  ], true);

  instructionSheet.getRange('A2:B5').setValues([
    ['ลิงก์แก้ไข Form', form.getEditUrl()],
    ['ลิงก์ให้ทีมกรอก', form.getPublishedUrl()],
    ['Response Spreadsheet', spreadsheet.getUrl()],
    ['สถานะ', 'สร้าง Form และเชื่อม Response แล้ว']
  ]);
  instructionSheet.autoResizeColumns(1, 2);
  SpreadsheetApp.flush();

  Logger.log('EDIT URL: ' + form.getEditUrl());
  Logger.log('RESPONDER URL: ' + form.getPublishedUrl());
}

function addPage(form, title, helpText) {
  form.addPageBreakItem().setTitle(title).setHelpText(helpText || '');
}

function addText(form, title, required, helpText) {
  const item = form.addTextItem().setTitle(title).setRequired(Boolean(required));
  if (helpText) item.setHelpText(helpText);
  return item;
}

function addParagraph(form, title, required, helpText) {
  const item = form.addParagraphTextItem().setTitle(title).setRequired(Boolean(required));
  if (helpText) item.setHelpText(helpText);
  return item;
}

function addChoice(form, title, choices, required) {
  return form.addMultipleChoiceItem().setTitle(title).setChoiceValues(choices).setRequired(Boolean(required));
}

function addCheckbox(form, title, choices, required) {
  return form.addCheckboxItem().setTitle(title).setChoiceValues(choices).setRequired(Boolean(required));
}

function addPackageQuestions(form, label) {
  form.addSectionHeaderItem().setTitle(label);
  addText(form, label + ': ชื่อแพ็กเกจ', false);
  addText(form, label + ': ราคาและรอบบิล', false);
  addParagraph(form, label + ': เหมาะกับใครและได้รับอะไร', false);
  addParagraph(form, label + ': Trial, Bonus, ระยะเวลาสิทธิ์ และข้อจำกัด', false);
  addText(form, label + ': Checkout URL', false);
}

function addOfferQuestions(form, label, type) {
  form.addSectionHeaderItem().setTitle(label);
  addText(form, label + ': สินค้าปัจจุบัน → ข้อเสนอ' + type, false);
  addParagraph(form, label + ': Trigger และช่วงเวลาที่เสนอ', false);
  addParagraph(form, label + ': ข้อความที่ Agent ใช้และ CTA', false);
  addParagraph(form, label + ': ถ้ารับ / ถ้าปฏิเสธ / ข้อห้าม', false);
}

function addFAQQuestions(form, number) {
  form.addSectionHeaderItem().setTitle('FAQ ' + number);
  addText(form, 'FAQ ' + number + ': หมวดและคำถามหลัก', false);
  addParagraph(form, 'FAQ ' + number + ': คำถามรูปแบบอื่นหรือ Keyword', false);
  addParagraph(form, 'FAQ ' + number + ': คำตอบที่อนุมัติ', false);
  addParagraph(form, 'FAQ ' + number + ': Next Action / Handoff / สิ่งที่ห้ามพูด', false);
}
