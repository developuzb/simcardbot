# Texnoset SIMCARD — Play Market'ga chiqarish bo'yicha qo'llanma

Bu papka (`pwa/`) saytni **Android ilova** sifatida Play Market'ga joylash uchun tayyor PWA paketi.

## Papkadagi fayllar
| Fayl | Vazifasi |
|------|----------|
| `index.html` | Mustaqil (offline ishlaydigan) to'liq sayt — bitta faylda |
| `manifest.json` | PWA manifesti (ilova nomi, ranglar, ikonalar) |
| `service-worker.js` | Offline keshlash (internetsiz ham ochiladi) |
| `icon-192.png`, `icon-512.png` | Ilova ikonalari |
| `icon-maskable-512.png` | Android adaptive (maskali) ikona |
| `apple-touch-icon.png`, `favicon-32.png` | iOS / brauzer ikonalari |
| `.well-known/assetlinks.json` | TWA tasdiqlash fayli (fingerprint kerak) |

---

## 1-qadam — Saytni internetga joylash (HTTPS)
Domeningiz: **sim.texnoset.uz**

`pwa/` papkasidagi barcha fayllarni shu domen ildiziga yuklang. Tavsiya etiladigan bepul hostinglar:
- **Netlify** — papkani sudrab tashlaysiz (drag & drop), darrov HTTPS beradi
- **Vercel** yoki **Cloudflare Pages**
- O'z serveringiz (HTTPS shart!)

Tekshiring: `https://sim.texnoset.uz/index.html` ochilsinmi va `https://sim.texnoset.uz/manifest.json` ko'rinsinmi.

> ⚠️ `.well-known/assetlinks.json` ham `https://sim.texnoset.uz/.well-known/assetlinks.json` manzilida ochilishi shart.

---

## 2-qadam — PWA'ni tekshirish
Chrome (telefon yoki kompyuter) orqali saytni oching → manzil satrida **"Ilovani o'rnatish"** belgisi chiqsa, PWA to'g'ri ishlayapti.

---

## 3-qadam — Android ilova (.aab) yasash — PWABuilder
1. [https://www.pwabuilder.com](https://www.pwabuilder.com) ga kiring
2. Sayt manzilini kiriting: `https://sim.texnoset.uz`
3. **Package For Stores → Android** ni tanlang
4. Sozlamalar:
   - **Package ID:** `uz.texnoset.sim`
   - **App name:** Texnoset — SIM yetkazish
   - **Signing key:** "Create new" (PWABuilder kalit yaratib beradi — **saqlab qo'ying!**)
5. **Generate** → `.aab` fayl va `assetlinks.json` (to'g'ri fingerprint bilan) yuklab olinadi

---

## 4-qadam — Digital Asset Links
PWABuilder bergan `assetlinks.json` ichidagi **SHA256 fingerprint** ni oling va ushbu papkadagi `.well-known/assetlinks.json` fayldagi `BU_YERGA...` o'rniga qo'ying, so'ng serverga qayta yuklang. Bu — ilova manzil satrisiz (to'liq ekran) ochilishi uchun zarur.

---

## 5-qadam — Google Play Console
1. [https://play.google.com/console](https://play.google.com/console) — developer akkaunt oching (bir martalik **$25**)
2. **Create app** → nom, til (o'zbek), kategoriya
3. **Production → Create release** → `.aab` faylni yuklang
4. Do'kon sahifasini to'ldiring:
   - Qisqa tavsif, to'liq tavsif
   - Skrinshotlar (telefon: kamida 2 ta)
   - Ilova ikonasi: `icon-512.png`
   - Feature grafika (1024×500) — alohida yasash kerak
5. Maxfiylik siyosati havolasi (Play talab qiladi)
6. **Tekshiruvga yuboring** — odatda 1–3 kun ichida tasdiqlanadi

---

## Android ilova uchun moslamalar (bajarilgan)
Ushbu paket Android (TWA) ilovasi uchun maxsus sozlangan:
- **Xavfsiz zona (safe-area)** — status bar / notch va jest paneli ostiga kontent kirmaydi (`env(safe-area-inset-*)`)
- **Native his** — bosishda kulrang yorqinlik yo'q, ortiqcha "cho'zilish" (bounce/pull-refresh) o'chirilgan
- **Fokusda zoom yo'q** — barcha input maydonlari 16px (Android avtomatik kattalashtirmaydi)
- **Status bar rangi** — to'q yashil (`#06382a`), oq ikonalar bilan
- **To'liq ekran** — `display: standalone`, vertikal (portrait) yo'nalish
- `index.html` — PWA qobig'i (manifest + SW), `app.html` — ilovaning o'zi

## Eslatmalar
- Sayt o'zgarsa, PWABuilder'da qayta paket yasash **shart emas** — TWA jonli saytni ko'rsatadi. Faqat `index.html` ni serverga yangilab qo'ysangiz, ilovada ham yangilanadi.
- iOS (App Store) uchun alohida jarayon kerak (TWA faqat Android uchun).
- Buyurtmalar hozir clipboard + Telegram orqali ketadi. Avtomatik serverga tushishi uchun keyinchalik backend ulash mumkin.
