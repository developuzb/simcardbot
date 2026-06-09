# SIM Karta Yetkazib Berish Boti

## O'rnatish

### 1. Loyihani yuklab olish
```bash
cd simcard_bot
pip install -r requirements.txt
```

### 2. .env fayl yaratish
```bash
cp .env.example .env
```
`.env` faylini oching va quyidagilarni to'ldiring:
- `BOT_TOKEN` — BotFather dan olingan token
- `ADMIN_IDS` — Admin Telegram ID (vergul bilan ajrating)
- `SPREADSHEET_ID` — Google Sheets ID (URL dagi qism)
- `SHEET_NAME` — Varaq nomi (default: Buyurtmalar)

### 3. Google Sheets sozlash

1. [Google Cloud Console](https://console.cloud.google.com) ga kiring
2. Yangi loyiha yarating
3. **Google Sheets API** va **Google Drive API** ni yoqing
4. **Service Account** yarating → JSON kalit yuklab oling
5. Faylni `credentials.json` nomi bilan bot papkasiga qo'ying
6. Google Sheets'ni oching → **Ulashish** → Service Account emailini qo'shing

### 4. Botni ishga tushirish
```bash
python bot.py
```

---

## Bot oqimi (Flow)

```
/start
  └─► Operator tanlash (5 ta)
        └─► Tarif tanlash (har bir uchun 4 ta)
              └─► Raqam tanlash (yoki tasodifiy)
                    └─► Ism kiritish
                          └─► Telefon kiritish
                                └─► Lokatsiya yuborish
                                      └─► Hudud aniqlanadi
                                            └─► Yetkazish narxi ko'rsatiladi
                                                  └─► Tasdiqlash → Google Sheets + Admin xabar
```

## Fayl tuzilmasi

```
simcard_bot/
├── bot.py              # Asosiy fayl
├── config.py           # Sozlamalar
├── states.py           # FSM holatlari
├── keyboards.py        # Klaviaturalar
├── data.py             # Operatorlar, tariflar, raqamlar
├── utils.py            # Hudud aniqlash, narx hisoblash
├── sheets_handler.py   # Google Sheets integratsiya
├── handlers/
│   ├── start.py        # /start va bosh menyu
│   ├── operator.py     # Operator tanlash
│   ├── tariff.py       # Tarif tanlash
│   ├── number.py       # Raqam tanlash, ism, telefon
│   └── location.py     # Lokatsiya + tasdiqlash
├── requirements.txt
└── .env.example
```
