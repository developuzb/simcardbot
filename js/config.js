/* ============================================================
   CONFIG — barcha sozlamalar SHU YERDA. Faqat shu faylni tahrirlang.
   ============================================================ */
window.CONFIG = {
  // Backend (sim.texnoset.uz Heroku):
  CHAT_API:  "https://sim.texnoset.uz/chat",   // AI suhbat
  LEAD_API:  "https://sim.texnoset.uz/lead",   // ism+telefon -> Telegram guruh

  // Aloqa:
  TELEGRAM:  "https://t.me/+998770097171",
  PHONE:     "+998 77 009 71 71",
  PHONE_TEL: "+998770097171",

  // Analitika (bo'sh bo'lsa o'chiq turadi — xato bermaydi):
  METRICA_ID: "",   // ← Yandex Metrica raqamini qo'ying, masalan "98765432"
  GA4_ID:     "",   // ← ixtiyoriy, masalan "G-XXXXXXX"

  // SEO / ulashish:
  OG_IMAGE:  "https://developuzb.github.io/simcardbot/assets/og.jpg", // placeholder (1200x630)
  SITE_URL:  "https://developuzb.github.io/simcardbot/",

  // Tanqislik (eksklyuzivlik bloki):
  REGION_SLOTS: 7,   // hududingizda qolgan o'rinlar (placeholder)

  // Narxlar (so'm):
  PRICES: {
    setup: 9999900,
    start: 390000,
    biznes: 690000,
    premium: 1200000,
    premium_yillik: 840000   // yillik to'lasa oylik ekvivalenti (2 oy bepul)
  },

  // Ijtimoiy isbot / count-up raqamlar:
  STATS: { businesses: 30, speed: 15 },

  // Chat xulq-atvori:
  CHAT: {
    leadAfterMessages: 3,   // necha mijoz xabaridan keyin ism+telefon so'rasin
    proactiveDelayMs: 12000 // necha ms dan keyin proaktiv bubble chiqsin
  },

  // Xususiyat bayroqlari:
  FLAGS: { proactiveBubble: true, exitIntent: true }
};
