# Saytdagi chatni haqiqiy AI qilish — qo'llanma

Sayt chati hozir **ssenariy (demo) rejimda** ishlaydi — buzilmaydi, hammaga ko'rinadi.
Quyidagi 3 qadamdan keyin u **haqiqiy sun'iy intellektga** ulanadi.

> Nega backend kerak? API kalitni to'g'ridan-to'g'ri saytga qo'yib bo'lmaydi —
> uni har kim ko'rib, o'g'irlab, hisobingizdan pul sarflashi mumkin.
> `chat_backend.py` kalitni serverda yashirin saqlaydi.

---

## 1-qadam — BEPUL AI kalit oling (Groq, 2 daqiqa)

Groq tez va bepul (boshlash uchun ideal):

1. https://console.groq.com ga kiring (Google bilan ro'yxatdan o'ting)
2. **API Keys** → **Create API Key**
3. Kalitni nusxalang — `gsk_...` bilan boshlanadi

> Xohlasangiz OpenAI ham bo'ladi (lekin pullik). U holda `LLM_BASE_URL` va `LLM_MODEL` ni o'zgartirasiz (kodda izoh bor).

---

## 2-qadam — Backendni ishga tushiring

### Variant A — kompyuterda sinab ko'rish
```bash
pip install flask flask-cors requests
set LLM_API_KEY=gsk_xxxxx        # Windows
python chat_backend.py
```
Server `http://localhost:8000` da ishlaydi. Tekshirish: brauzerda `http://localhost:8000/health` oching.

### Variant B — bepul internetga joylash (Render.com)
1. Kodni GitHub'ga yuklang (yoki mendan yordam so'rang)
2. https://render.com → **New → Web Service** → repo'ni tanlang
3. **Start command:** `python chat_backend.py`
4. **Environment** bo'limida `LLM_API_KEY = gsk_xxxxx` qo'shing
5. Deploy bo'lgach manzil olasiz: `https://sizning-nomi.onrender.com`

---

## 3-qadam — Saytga ulang

`sotuv_landing.html` faylini oching, chat kodidagi shu qatorni toping:
```js
var CHAT_API = "";
```
va backend manzilingizni yozing:
```js
var CHAT_API = "https://sizning-nomi.onrender.com/chat";
```
Saqlang — tamom! Endi chat haqiqiy AI bilan javob beradi.
Agar backend o'chsa yoki xato bo'lsa, chat avtomatik ssenariy rejimga qaytadi (sayt buzilmaydi).

---

## Sozlamalar (env, ixtiyoriy)

| O'zgaruvchi | Vazifasi | Default |
|---|---|---|
| `LLM_API_KEY` | AI kaliti (majburiy) | — |
| `LLM_BASE_URL` | AI provayder manzili | Groq |
| `LLM_MODEL` | Model nomi | llama-3.3-70b-versatile |
| `ALLOW_ORIGIN` | Faqat sayt domeningizga ruxsat (xavfsizroq) | `*` |
| `PORT` | Server porti | 8000 |

## Xarajat nazorati
- Groq bepul limit bilan keladi — boshlash uchun yetarli.
- Backendda har IP uchun oddiy "sekinlashtirish" (rate-limit) bor — suiiste'molni kamaytiradi.
- Agar mijozlar ko'paysa, OpenAI yoki pullik Groq planiga o'tasiz.

## Muhim eslatma
Agentning "miyasi" (tariflar, sotuv uslubi) `chat_backend.py` ichidagi `SYSTEM_PROMPT` da.
Tariflar o'zgarsa yoki sotuv uslubini o'zgartirmoqchi bo'lsangiz — faqat shu matnni tahrirlang.
