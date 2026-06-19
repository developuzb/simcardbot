# Texnoset — Deploy qo'llanmasi (GitHub + Heroku + Groq)

> ⚠️ **Men (Claude) sizning GitHub yoki Heroku akkauntingizga kira olmayman** —
> push qilish va domen band qilish SIZNING login/parolingiz bilan bo'ladi.
> Quyida har bir buyruq tayyor — nusxalab bajaring. Men yordam beraman.

**Arxitektura:**
- 🌐 **Sayt** (`sotuv_landing.html`) → GitHub → bepul hosting (GitHub Pages / Netlify)
- 🤖 **Agent** (`agent/` papkasi) → Heroku → **agent.texnoset.uz**
- 🧠 **Groq** → agentning sun'iy intellekti (bepul kalit)

---

## ⚠️ 0-qadam — Maxfiylikni tekshiring (MUHIM!)

`.gitignore` allaqachon `.env`, `credentials.json` va mijoz ma'lumotlarini himoyalaydi.
Lekin **agar `.env` ilgari git'ga qo'shilgan bo'lsa**, u tarixda qoladi. Tekshiring:
```bash
git ls-files | findstr ".env"
```
Agar `.env` chiqsa — push qilishdan oldin meni ogohlantiring, tarixdan tozalaymiz.

---

## A — Saytni GitHub'ga push qilish

Eng oson: faqat sayt fayli uchun alohida repo.

1. `sotuv_landing.html` nusxasini oling va **`index.html`** deb nomlang (GitHub Pages root'da shuni ko'rsatadi).
2. Yangi papka oching (masalan `texnoset-web`), `index.html` ni ichiga qo'ying.
3. GitHub'da yangi repo yarating: github.com → **New repository** → nomi `texnoset-web` → **Private** (tavsiya).
4. Terminal (PowerShell) `texnoset-web` papkasida:
```bash
git init
git add index.html
git commit -m "Texnoset sayti"
git branch -M main
git remote add origin https://github.com/SIZNING_USERNAME/texnoset-web.git
git push -u origin main
```
5. **Jonli qilish:** repo → **Settings → Pages → Branch: main → Save.** Sayt `https://SIZNING_USERNAME.github.io/texnoset-web/` da ochiladi.

> 💡 Eng oson muqobil (GitHub'siz): [netlify.com](https://netlify.com) ga `index.html` ni **sudrab tashlang** — bir zumda jonli sayt + bepul domen.

---

## B — Agentni Heroku'ga + agent.texnoset.uz

> 💵 **Eslatma:** Heroku'da bepul tarif yo'q (~$5–7/oy "Eco" dyno). Bepul muqobil — [Render.com](https://render.com). Pastdagi qadamlar Heroku uchun.

### B1. Tayyorlash
- Heroku akkaunt: [signup.heroku.com](https://signup.heroku.com) (karta tasdiqlanadi).
- Heroku CLI o'rnating: [devcenter.heroku.com/articles/heroku-cli](https://devcenter.heroku.com/articles/heroku-cli)
- **Groq kalit** oling: [console.groq.com](https://console.groq.com) → API Keys → Create → `gsk_...`

### B2. Deploy (terminal `agent/` papkasida)
```bash
cd agent
heroku login
heroku create texnoset-agent
heroku config:set LLM_API_KEY=gsk_xxxxx
git init
git add .
git commit -m "Sotuv agenti backend"
git branch -M main
git push heroku main
```
Tekshirish: `https://texnoset-agent.herokuapp.com/health` → `{"ok":true,...}` chiqishi kerak.

### B3. agent.texnoset.uz domenini ulash
```bash
heroku domains:add agent.texnoset.uz
```
Bu buyruq sizga **DNS Target** beradi, masalan: `xyz123.herokudns.com`

Endi **texnoset.uz domen boshqaruvi**ga (registrator yoki Cloudflare) kiring va yozuv qo'shing:
| Turi | Nomi | Qiymat |
|---|---|---|
| CNAME | `agent` | `xyz123.herokudns.com` (Heroku bergan qiymat) |

SSL (https) yoqish:
```bash
heroku certs:auto:enable
```
DNS tarqalishi 5 daqiqa–1 soat. So'ng `https://agent.texnoset.uz/health` ishlashini tekshiring.

> 🔒 Xavfsizlik: domen ishlagach, faqat saytingizga ruxsat bering:
> `heroku config:set ALLOW_ORIGIN=https://texnoset.uz`

---

## C — Saytni agentga ulash

`sotuv_landing.html` (yoki `index.html`) ichida chat kodidagi qatorni toping:
```js
var CHAT_API = "";
```
va shunday yozing:
```js
var CHAT_API = "https://agent.texnoset.uz/chat";
```
Saqlang, saytni qayta push qiling. Tamom — chat endi haqiqiy AI bilan javob beradi! 🎉
Agent o'chsa, chat avtomatik ssenariy rejimga qaytadi (sayt buzilmaydi).

---

## Tartib (qisqacha)
1. ✅ `.env` git'da emasligini tekshirish
2. 🌐 Saytni GitHub'ga push → jonli qilish
3. 🧠 Groq kalit olish
4. 🤖 Agentni Heroku'ga push + kalitni qo'yish
5. 🔗 agent.texnoset.uz CNAME + SSL
6. 🔌 Saytdagi `CHAT_API` ga manzilni yozish

Har qadamda yordam kerak bo'lsa — qaysi qadamdaligingizni ayting, birga o'tamiz.
