# Texnoset AI — sotuv landing (CRO)

SIM-karta dilerlari uchun sun'iy intellektli sotuv agentini sotadigan **static** landing sahifa.
Maqsad: tashrif buyuruvchini jonli botga tortib, ism+telefon ushlab, Telegramga konversiya qilish.

## Tuzilma

```
index.html        markup + inline kritik CSS + OG/meta
css/styles.css    bo'lim stillari + chat vidjeti
js/config.js      ⚙️ BARCHA sozlama shu yerda
js/analytics.js   Yandex Metrica + GA4 + track()
js/chat.js        bot vidjeti + lead-capture + halol degradatsiya
js/main.js        animatsiya, count-up, narx toggle, sticky CTA, treking
assets/og.jpg     1200×630 ulashish rasmi (tayyor; og.svg — manba)
assets/favicon.svg
```

## Deploy (GitHub Pages)

Bu papka tarkibini `gh-pages` branch'iga (root) joylash kifoya. Loyiha ildizidan:

```bash
git subtree push --prefix landing origin gh-pages   # yoki worktree bilan nusxalash
```

Sayt: `https://developuzb.github.io/simcardbot/`

> Backend (`/chat`, `/lead`) — `sim.texnoset.uz` (Heroku). Sayt static, backend alohida.

## To'ldirilishi kerak bo'lgan placeholderlar (`js/config.js`)

| Kalit | Nima |
|---|---|
| `METRICA_ID` | Yandex Metrica raqami (analitika yoqilishi uchun) — **majburiy** |
| `GA4_ID` | Google Analytics 4 (ixtiyoriy) |
| `REGION_SLOTS` | Eksklyuzivlik blokidagi "qolgan o'rin" soni |
| `STATS.businesses` | Ijtimoiy isbotdagi biznes soni |
| `assets/og.jpg` | Tayyor, lekin xohlasangiz `assets/og.svg`ni tahrirlab qayta eksport qiling |

Otziv matnlari/ismlari — `index.html` ichidagi `#isbot` bo'limida (hozir namuna).
Demo video — `#isbot` dagi `.video-slot` (hozir placeholder).

## Backend (allaqachon Heroku'da)

- `POST /chat`  → AI suhbat (OpenAI gpt-5.4-mini, `chat_ai.py`)
- `POST /lead`  → `{name, phone, source, plan}` → operator **Telegram** chatiga (`web_server.py` → `_send_lead_to_telegram`)
  - Heroku config: `LEAD_CHAT_ID` (lead tushadigan chat; bo'lmasa `COURIER_GROUP_ID`/admin), `BOT_TOKEN` (bot.py bilan bir xil)

## Analitika hodisalari (qayerda ishga tushadi)

| Hodisa | Qachon |
|---|---|
| `chat_open` | Bot oynasi birinchi marta ochilganda |
| `chat_message_sent` | Mijoz har xabar yuborganda |
| `plan_selected` | Narx kartasidagi tugma bosilganda (`{plan}`) |
| `lead_submitted` | Ism+telefon yuborilganda (`{plan, ok}`) |
| `telegram_click` | Har qanday Telegram tugmasi |
| `scroll_depth` | 25/50/75/100% scroll |
| `section_view` | demo / narx / isbot / eksklyuziv ko'rilganda |
| `chat_error` | Backend yiqilib, lead-formaga pasayilganda |

`track(event, params)` — `analytics.js` da. Metrica/GA4 ID bo'lmasa jim no-op (xato bermaydi), lekin konsolda `[track]` ko'rinadi.

## Konversiya mexanikasi (qisqacha)

- **Har bir "Sinab ko'rish" / narx tugmasi** botni ochadi (`data-openchat`). O'lik link yo'q.
- Bot **3 xabardan keyin yoki xarid niyati** sezilganda ism+telefon so'raydi.
- **Backend yiqilsa** — jim ssenariy emas: "Operatorga ulayapman, raqamingizni qoldiring" lead-forma.
- Proaktiv bubble, exit-intent, mobil sticky CTA, count-up, reveal — konversiya uchun.
- JS o'chiq bo'lsa: raqamlar yakuniy qiymatda, CTAlar Telegram/telefonga ishlaydi.

## Mahalliy sinov

```bash
cd landing && python -m http.server 8090
# http://localhost:8090
```
> Lokalda `/chat` va `/lead` `sim.texnoset.uz`ga boradi (CORS ruxsat etilgan). Faqat dizaynni ko'rish uchun backend shart emas — chat halol degradatsiya bilan lead-formaga tushadi.
