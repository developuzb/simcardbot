# Texnoset SIM — sim.texnoset.uz uchun web sayt prompti

> Quyidagi matnni to'liq nusxalab, biriktirilgan **logo bilan birga** Claude'ga (Claude Design) yuboring.

---

Sen tajribali UI/UX dizayner va frontend dasturchisan. Men SIM karta uyga yetkazib berish xizmati uchun **zamonaviy, konversiyaga yo'naltirilgan, bitta sahifali (one-page) responsiv web sayt** yaratishingni xohlayman. Logotipni biriktirdim — **rang palitrasini aynan shu logodan ol** va butun saytni shu brendga moslab qil.

## Biznes haqida
- **Nomi:** Texnoset
- **Xizmat:** O'zbekistondagi barcha operatorlar SIM kartasini **eshikkacha yetkazib berish**
- **Hudud:** Qashqadaryo, Qarshi tumani, Qovchin va atrofi
- **Domen:** sim.texnoset.uz
- **Til:** o'zbek (lotin) — butun sayt o'zbekcha
- **Auditoriya:** asosan telefondan kiradi → **mobile-first** (avval mobil, keyin desktop)
- **Telegram bot (asosiy buyurtma kanali):** https://t.me/texnoset_onlayn_bot

## Brend va dizayn talablari
- Rang palitra **biriktirilgan logodan** olinadi (asosiy + ikkilamchi + urg'u rangi)
- Zamonaviy, toza, ishonchli va "tez" his beradigan dizayn
- Yumaloq burchakli kartochkalar, yengil soyalar, ko'p "havo" (bo'sh joy)
- O'rinli ikonkalar/emoji, chiroyli tipografika (masalan Inter yoki Manrope shrifti)
- Silliq animatsiyalar (scroll-reveal, hover effektlar) — lekin yengil, tez
- **Yagona, mustaqil fayl:** HTML + ichki CSS + minimal JS (faqat font/ikona uchun CDN ruxsat). Tashqi backend yo'q
- SEO: o'zbekcha `<title>`, meta description, Open Graph (ijtimoiy tarmoqda chiroyli ko'rinishi uchun), `lang="uz"`
- Tez yuklanishi va A+ mobil ko'rinish

## Asosiy maqsad (CTA)
Saytning bosh maqsadi — odamni **Telegram botga buyurtmaga** yo'naltirish.
- Har bo'limda yorqin tugma: **«🛒 Telegramda buyurtma berish»** → https://t.me/texnoset_onlayn_bot
- Mobil ekranda doimo ko'rinib turadigan **sticky (yopishqoq) CTA tugma** pastda
- Ikkilamchi tugma: **«📞 Qo'ng'iroq»** → tel:+998770097171

## Sahifa bo'limlari (tartibi bilan)

1. **Hero (yuqori ekran)**
   - Logo
   - Sarlavha: «SIM kartani eshigingizgacha yetkazamiz»
   - Tag: «Barcha operatorlar • Bugun buyurtma — bugun qo'lingizda • To'lov topshirilganda»
   - Katta CTA tugma + ikkilamchi qo'ng'iroq tugmasi
   - Ishonch chizig'i: «✅ Rasmiy SIM · Pasport bilan rasmiylashtiriladi · Yoqmasa — olishingiz shart emas»

2. **Operatorlar** — beshta brend belgisi/kartochkasi: Ucell, Beeline, Mobiuz, Humans, Uzmobile

3. **Aksiyalar** (e'tiborni tortadigan kartochkalar)
   - 🎁 **1+1:** 70 000 so'm va undan qimmat tariflarga **ikkinchi SIM BEPUL**
   - 🚚 **Bepul yetkazish** (6 soat ichida)
   - 👥 **Do'st taklif qil** — do'stingiz havola orqali kelsa, birinchi buyurtmasiga chegirma

4. **Tariflar** — operator bo'yicha kartochkalar (GB · qo'ng'iroq · SMS · narx). 70 000+ larga «1+1» nishoni. Namuna ma'lumotlar (so'm/oy):
   - **Ucell:** Foydali 45 — 25 GB, 700 daq, 700 SMS · Bor 70 — 140 GB, cheksiz qo'ng'iroq · Bor 110 — 300 GB
   - **Beeline:** Standart 45 — 25 GB · Multi Plus 65 — 40 GB + ChatGPT/Claude cheksiz · Yorqin 70 — cheksiz internet
   - **Mobiuz:** Connect M 45 — 25 GB · Mazza 70 — 150 GB, ijtimoiy tarmoqlar cheksiz · ORZU 90 — 180 GB
   - **Humans:** Cheksiz qo'ng'iroq (3 oy) — 50 000 · Aloqa+Internet — 65 000
   - **Uzmobile:** Mini M 45 — 10 GB · Bonus Super Salom 70 — 100 GB, YouTube bepul · Super Lux 77 — 200 GB
   - Kartochka tagida: «To'liq tariflar va buyurtma — Telegram botda» tugmasi

5. **Qanday ishlaydi** (4–5 qadam, ikonka bilan)
   1. Telegram botda operator va tarifni tanlaysiz (AI yordamchi yordam beradi)
   2. Telefon raqami va joylashuvni yuborasiz
   3. Kuryer SIM kartalar bilan eshigingizga keladi
   4. Raqamni oldindan kelishasiz yoki kuryer oldida tanlaysiz
   5. Pasport bilan rasmiylashtiriladi, to'lovni topshirilganda qilasiz (naqd yoki karta)

6. **Yetkazish turlari**
   - 🆓 Bepul yetkazish — 6 soat ichida
   - ⚡ Tezkor — 1 soat ichida (10 000 so'm)
   - 🚗 Standart — 2 soat ichida (5 000 so'm)

7. **Nega Texnoset? (ishonch)**
   - Rasmiy SIM, pasport bilan rasmiylashtiriladi
   - To'lov SIM qo'lingizga tekkanda (naqd yoki karta)
   - Yoqmasa olishingiz shart emas — xavf yo'q
   - Tez va qulay, eshikkacha

8. **Aloqa / Footer**
   - Telefon: +998 77 009 71 71
   - Telegram: @texnoset_digital
   - Asoschi: @aflaha_s
   - Manzil: Qashqadaryo, Qarshi tumani, Qovchin shaharchasi
   - Ish vaqti: har kuni 09:00–21:00
   - Asosiy CTA yana bir marta

## Uslub (tone)
Iliq, ishonchli, mahalliy. Ortiqcha texnik atamalarsiz, sodda va aniq. Har bo'lim qisqa va o'qishga oson bo'lsin.

## Natija
Tayyor, ko'chirib qo'yishga shay bitta `index.html` fayl ber (ichida CSS va JS). Sayt `sim.texnoset.uz` ga joylashtiriladi — shuni hisobga olib meta teglar va kanonik URL'ni shunga moslab qo'y.
