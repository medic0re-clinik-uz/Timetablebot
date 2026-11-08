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
| /toxtatish | eslatmalarni o'chirish |

## Sozlamalar (`.env`)
`MORNING_TIME` (07:00), `REMIND_MINUTES` (10), `TIMEZONE` (Asia/Tashkent),
`SEND_ON_FREE_DAYS` (1 = darssiz kunda ham xabar yuboradi, 0 = yubormaydi).

## Jadval o'zgarsa
```bash
python extract_schedule.py YangiJadval.xlsx 25-407
```
`schedule.json` yangilanadi, so'ng botni qayta ishga tushiring.
