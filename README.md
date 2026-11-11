# 📚 25-407 dars jadvali boti

Telegram bot: har kuni 07:00 da bugungi darslarni yuboradi, har dars boshlanishidan 10 daqiqa oldin eslatadi,
**Bugun / Ertaga / Bu hafta / Keyingi dars** tugmalari bor. Sayt kerak emas.

## 1. Token olish
1. Telegramda **@BotFather** ga yozing → `/newbot`
2. Bot nomi va username (oxiri `bot` bilan tugashi kerak) bering
3. Bergan **token**ni nusxalang

## 2. Ishga tushirish
```bash
pip install -r requirements.txt
cp .env.example .env        # keyin .env ichiga BOT_TOKEN ni yozing
python bot.py
```
Botga kirib `/start` bosing — eslatmalar yoqiladi.

> ⚠️ Eslatma yuborishi uchun `bot.py` **doim ishlab turishi** kerak (kompyuter yoniq yoki serverda).
> Kompyuter o'chiq bo'lsa, eslatmalar kelmaydi.

## Buyruqlar
| Buyruq | Vazifa |
|---|---|
| /start | botni yoqish, eslatmalarga obuna |
| /bugun, /ertaga, /hafta, /keyingi | darslarni ko'rish |
| /xonalar (🚪 Bo'sh xonalar) | bugun guruh darsi tugagach kun oxirigacha bo'sh xonalar |
| /toxtatish | eslatmalarni o'chirish |

## Sozlamalar (`.env`)
`MORNING_TIME` (07:00), `REMIND_MINUTES` (10), `TIMEZONE` (Asia/Tashkent),
`SEND_ON_FREE_DAYS` (1 = darssiz kunda ham xabar yuboradi, 0 = yubormaydi).

## Jadval o'zgarsa
```bash
python extract_schedule.py YangiJadval.xlsx 25-407
```
`schedule.json` (guruh darslari) va `rooms.json` (barcha guruhlar bo'yicha xonalar bandligi) yangilanadi. So'ng GitHub'ga push qilib, Render'da Manual Deploy bosing.

## 24/7 ishlatish (Render, bepul)
1. Kodni GitHub'ga yuklang (`.env` yuklanmaydi).
2. Render → New → **Web Service** → shu repo. Runtime: **Python 3**.
   Build Command: `pip install -r requirements.txt`  ·  Start Command: `python bot.py`  ·  Plan: **Free**.
3. Environment bo'limida: `BOT_TOKEN` (BotFather tokeni) va `SUBSCRIBERS` (sizning Telegram ID raqamingiz).
4. UptimeRobot'da `https://<servis-nomi>.onrender.com/` manzilini har 5 daqiqada tekshiradigan monitor qo'shing
   (Render bepul servisi 15 daqiqada uxlab qoladi, monitor uni uyg'oq tutadi).
5. Shu bot tokeni bilan boshqa joyda (kompyuteringizda) `bot.py` ishlamayotgan bo'lsin, aks holda "409 Conflict" xatosi chiqadi.

> Render bepul tarifida fayllar qayta ishga tushganda o'chadi, shuning uchun doimiy obunachilar `SUBSCRIBERS` da turadi.
