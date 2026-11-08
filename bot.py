"""25-407 guruh uchun dars jadvali eslatuvchi Telegram bot.

Imkoniyatlar:
  * har kuni 07:00 da shu kunning darslari (vaqt, xona, o'qituvchi) yuboriladi
  * har bir dars boshlanishidan 10 daqiqa oldin eslatma keladi
  * tugmalar / buyruqlar: Bugun, Ertaga, Bu hafta, Keyingi dars
"""
from __future__ import annotations

import html
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telegram import (
    BotCommand,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

BASE = Path(__file__).parent
load_dotenv(BASE / ".env")

TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Tashkent"))
MORNING_AT = time.fromisoformat(os.getenv("MORNING_TIME", "07:00"))
REMIND_MIN = int(os.getenv("REMIND_MINUTES", "10"))
SEND_ON_FREE_DAYS = os.getenv("SEND_ON_FREE_DAYS", "1") == "1"
STATE_FILE = Path(os.getenv("STATE_FILE", BASE / "state.json"))
TICK_SECONDS = 30  # jadval har 30 soniyada tekshiriladi
GRACE_SECONDS = 120  # bot biroz kechiksa ham eslatma yuboriladi, lekin undan keyin emas

log = logging.getLogger("dars-bot")

# --------------------------------------------------------------------------- #
#  Matnlar
# --------------------------------------------------------------------------- #
DAY_NAMES = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun",
          "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]

BTN_TODAY, BTN_TOMORROW = "📅 Bugun", "🌅 Ertaga"
BTN_WEEK, BTN_NEXT = "🗓 Bu hafta", "⏭ Keyingi dars"

SUBJECT_ICONS = [
    ("python", "🐍"), ("java", "☕"), ("big data", "📊"), ("database", "🗄"),
    ("english", "🇬🇧"), ("professional practice", "💼"), ("math", "📐"),
    ("ai", "🤖"), ("cloud", "☁️"),
]
SUBJECT_UZ = {"Practice": "Amaliyot", "Lecture": "Ma'ruza"}


def fmt_date(d: date) -> str:
    return f"{DAY_NAMES[d.weekday()]}, {d.day}-{MONTHS[d.month - 1]}"


def e(s: str) -> str:
    return html.escape(s, quote=False)


# --------------------------------------------------------------------------- #
#  Jadval
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Lesson:
    day: int  # 0 = dushanba
    start: time
    end: time
    subject: str
    teacher: str
    room: str
    groups: tuple[str, ...]

    @property
    def title(self) -> str:
        return re.sub(r"\s*\((Practice|Lecture)\)\s*$", "", self.subject).strip()

    @property
    def kind(self) -> str | None:
        m = re.search(r"\((Practice|Lecture)\)\s*$", self.subject)
        return SUBJECT_UZ[m.group(1)] if m else None

    @property
    def icon(self) -> str:
        low = self.subject.lower()
        for key, icon in SUBJECT_ICONS:
            if key in low:
                return icon
        return "📘"

    @property
    def room_uz(self) -> str:
        m = re.match(r"^(\d+)\s*(.*)$", self.room)
        if not m:
            return self.room or "—"
        num, rest = m.groups()
        rest = rest.lower()
        if "lecture" in rest:
            return f"{num}-xona (ma'ruza zali)"
        if "lab" in rest:
            return f"{num}-xona (laboratoriya)"
        return f"{num}-xona"

    def hours(self, sep: str = "–") -> str:
        return f"{self.start:%H:%M} {sep} {self.end:%H:%M}"

    def start_dt(self, d: date) -> datetime:
        return datetime.combine(d, self.start, tzinfo=TZ)

    def end_dt(self, d: date) -> datetime:
        return datetime.combine(d, self.end, tzinfo=TZ)

    def shared_with(self, own_group: str) -> list[str]:
        return [g.split(" ")[0] for g in self.groups if g.split(" ")[0] != own_group]


def load_schedule(path: Path = BASE / "schedule.json") -> tuple[str, list[Lesson]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    lessons = [
        Lesson(
            day=l["day"],
            start=time.fromisoformat(l["start"]),
            end=time.fromisoformat(l["end"]),
            subject=l["subject"],
            teacher=l["teacher"],
            room=l["room"],
            groups=tuple(l.get("groups", [])),
        )
        for l in data["lessons"]
    ]
    lessons.sort(key=lambda l: (l.day, l.start))
    return data["group"], lessons


GROUP, LESSONS = load_schedule()


def lessons_on(d: date) -> list[Lesson]:
    return [l for l in LESSONS if l.day == d.weekday()]


def next_lesson(now: datetime) -> tuple[date, Lesson] | None:
    for offset in range(8):
        d = now.date() + timedelta(days=offset)
        for l in lessons_on(d):
            if l.start_dt(d) > now:
                return d, l
    return None


# --------------------------------------------------------------------------- #
#  Xabar dizayni
# --------------------------------------------------------------------------- #
def fmt_gap(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    return " ".join(p for p in [f"{h} soat" if h else "", f"{m} daqiqa" if m else ""] if p)


def fmt_left(delta: timedelta) -> str:
    total_min = max(int(delta.total_seconds()) // 60, 0)
    days, rem = divmod(total_min, 1440)
    h, m = divmod(rem, 60)
    return " ".join(p for p in [f"{days} kun" if days else "", f"{h} soat" if h else "",
                                f"{m} daqiqa" if m or not (days or h) else ""] if p)


def lesson_card(l: Lesson, idx: int | None = None, status: str = "") -> str:
    """Bitta dars — Telegram <blockquote> kartochkasi."""
    num = f"{idx}. " if idx else ""
    meta = []
    if l.kind:
        meta.append(f"🏷 {l.kind}")
    others = l.shared_with(GROUP)
    if others:
        meta.append(f"👥 Birga: {e(', '.join(others))}")
    lines = [
        f"{l.icon} <b>{num}{e(l.title)}</b>{status}",
        f"🕘 <b>{l.hours()}</b> · 🚪 <b>{e(l.room_uz)}</b>",
        f"👨‍🏫 {e(l.teacher)}",
    ]
    if meta:
        lines.append("  ".join(meta))
    return "<blockquote>" + "\n".join(lines) + "</blockquote>"


def lesson_status(l: Lesson, d: date, now: datetime) -> str:
    if d != now.date():
        return ""
    if now >= l.end_dt(d):
        return "  ✅"
    if now >= l.start_dt(d):
        return "  🔴 <i>davom etmoqda</i>"
    return ""


def gap_line(prev: Lesson, nxt: Lesson) -> str:
    gap = (datetime.combine(date.min, nxt.start) - datetime.combine(date.min, prev.end)).seconds // 60
    if gap <= 10:
        return ""
    icon = "🍽" if gap >= 60 else "☕"
    return f"<i>{icon} Tanaffus — {fmt_gap(gap)}</i>"


def day_title(d: date, now: datetime) -> str:
    if d == now.date():
        return "☀️ BUGUNGI DARSLAR"
    if d == now.date() + timedelta(days=1):
        return "🌅 ERTANGI DARSLAR"
    return f"📅 {DAY_NAMES[d.weekday()].upper()} DARSLARI"


def day_message(d: date, now: datetime, *, morning: bool = False) -> str:
    items = lessons_on(d)
    head = f"<b>{day_title(d, now)}</b>\n📆 <i>{fmt_date(d)}</i>"

    if not items:
        return f"{head}\n\n🎉 <b>Darslar yo'q</b> — dam oling!"

    out = [head, f"\n🎯 <b>{len(items)} ta dars</b> · {items[0].start:%H:%M} dan {items[-1].end:%H:%M} gacha\n"]
    for i, l in enumerate(items, 1):
        if i > 1:
            gap = gap_line(items[i - 2], l)
            if gap:
                out.append(gap)
        out.append(lesson_card(l, i, lesson_status(l, d, now)))
    out.append(f"\n📋 <b>Jami: {len(items)} ta dars</b>")
    if morning:
        out.append("\n<i>Xayrli tong! Kuningiz samarali o'tsin 💪</i>")
    return "\n".join(out)


def week_message(now: datetime) -> str:
    monday = now.date() - timedelta(days=now.weekday())
    parts = [f"<b>🗓 BU HAFTA</b> · {GROUP} guruh"]
    total = 0
    for i in range(7):
        d = monday + timedelta(days=i)
        items = lessons_on(d)
        if not items:
            continue
        total += len(items)
        mark = "  👈 <b>bugun</b>" if d == now.date() else ""
        rows = []
        for l in items:
            k = f" ({l.kind})" if l.kind else ""
            done = " ✅" if d < now.date() or (d == now.date() and now >= l.end_dt(d)) else ""
            rows.append(
                f"🕘 <b>{l.start:%H:%M}–{l.end:%H:%M}</b>{done}\n"
                f"{l.icon} {e(l.title)}{k}\n"
                f"🚪 {e(l.room_uz)} · 👨‍🏫 {e(l.teacher)}"
            )
        parts.append(
            f"\n📌 <b>{DAY_NAMES[d.weekday()]}</b> · {d.day}-{MONTHS[d.month - 1]}{mark}\n"
            "<blockquote>" + "\n\n".join(rows) + "</blockquote>"
        )
    parts.append(f"\n📋 <b>Haftada jami: {total} ta dars</b>")
    return "\n".join(parts)


def reminder_message(l: Lesson, minutes: int) -> str:
    return (
        f"⏰ <b>{minutes} daqiqadan so'ng dars boshlanadi!</b>\n\n"
        f"{lesson_card(l)}\n\n"
        f"🏃 <i>Tayyorlaning — vaqt bor, lekin ko'p emas!</i>"
    )


def next_message(now: datetime) -> str:
    found = next_lesson(now)
    if not found:
        return "🎉 Yaqin kunlarda darslar topilmadi."
    d, l = found
    return (
        f"⏭ <b>KEYINGI DARS</b> · {fmt_left(l.start_dt(d) - now)} so'ng\n"
        f"📆 <i>{fmt_date(d)}</i>\n\n"
        f"{lesson_card(l)}"
    )


WELCOME = (
    "👋 <b>Salom!</b> Men <b>{group}</b> guruhining dars jadvali yordamchisiman.\n\n"
    "Men sizga:\n"
    "🌅 har kuni <b>{morning:%H:%M}</b> da bugungi darslarni yuboraman\n"
    "⏰ har bir dars boshlanishidan <b>{remind} daqiqa</b> oldin eslataman\n\n"
    "Quyidagi tugmalar yoki buyruqlardan foydalaning:\n"
    "/bugun · /ertaga · /hafta · /keyingi\n"
    "/toxtatish — eslatmalarni o'chirish\n\n"
    "✅ Eslatmalar <b>yoqildi</b>."
)

# --------------------------------------------------------------------------- #
#  Holat (obunachilar + yuborilgan eslatmalar)
# --------------------------------------------------------------------------- #
def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"subscribers": [], "sent": []}


def save_state(state: dict) -> None:
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE_FILE)


# --------------------------------------------------------------------------- #
#  Rejalashtirish mantig'i (sof funksiya — test qilish oson)
# --------------------------------------------------------------------------- #
def due_events(now: datetime, sent: set[str]) -> list[tuple[str, str, Lesson | None]]:
    """Hozir yuborilishi kerak bo'lgan xabarlar: [(kalit, tur, dars)]."""
    out: list[tuple[str, str, Lesson | None]] = []
    today = now.date()

    def in_window(target: datetime) -> bool:
        return 0 <= (now - target).total_seconds() < GRACE_SECONDS

    morning_key = f"{today}|morning"
    if morning_key not in sent and in_window(datetime.combine(today, MORNING_AT, tzinfo=TZ)):
        if SEND_ON_FREE_DAYS or lessons_on(today):
            out.append((morning_key, "morning", None))

    for l in lessons_on(today):
        key = f"{today}|{l.start:%H:%M}"
        if key not in sent and in_window(l.start_dt(today) - timedelta(minutes=REMIND_MIN)):
            out.append((key, "reminder", l))
    return out


# --------------------------------------------------------------------------- #
#  Telegram
# --------------------------------------------------------------------------- #
KEYBOARD = ReplyKeyboardMarkup(
    [[BTN_TODAY, BTN_TOMORROW], [BTN_WEEK, BTN_NEXT]],
    resize_keyboard=True,
    input_field_placeholder="Tugmani tanlang 👇",
)


async def reply(update: Update, text: str) -> None:
    await update.effective_message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=KEYBOARD, disable_web_page_preview=True
    )


def now_local() -> datetime:
    return datetime.now(TZ)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = context.application.bot_data["state"]
    cid = update.effective_chat.id
    if cid not in state["subscribers"]:
        state["subscribers"].append(cid)
        save_state(state)
    await reply(update, WELCOME.format(group=GROUP, morning=MORNING_AT, remind=REMIND_MIN))


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    state = context.application.bot_data["state"]
    cid = update.effective_chat.id
    if cid in state["subscribers"]:
        state["subscribers"].remove(cid)
        save_state(state)
    await reply(update, "🔕 Eslatmalar <b>o'chirildi</b>.\nQayta yoqish uchun /start ni bosing.\n"
                        "Tugmalar esa ishlashda davom etadi.")


async def cmd_today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    n = now_local()
    await reply(update, day_message(n.date(), n))


async def cmd_tomorrow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    n = now_local()
    await reply(update, day_message(n.date() + timedelta(days=1), n))


async def cmd_week(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await reply(update, week_message(now_local()))


async def cmd_next(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await reply(update, next_message(now_local()))


async def tick(context: ContextTypes.DEFAULT_TYPE) -> None:
    state = context.application.bot_data["state"]
    now = now_local()
    today = str(now.date())
    state["sent"] = [k for k in state["sent"] if k.startswith(today)]  # eskilarini tozalash
    events = due_events(now, set(state["sent"]))
    if not events:
        return
    for key, kind, lesson in events:
        state["sent"].append(key)
        text = (
            day_message(now.date(), now, morning=True)
            if kind == "morning"
            else reminder_message(lesson, REMIND_MIN)
        )
        for cid in list(state["subscribers"]):
            try:
                await context.bot.send_message(
                    cid, text, parse_mode=ParseMode.HTML, reply_markup=KEYBOARD
                )
            except Exception as exc:  # bot bloklangan va h.k.
                log.warning("Yuborib bo'lmadi (%s): %s", cid, exc)
                if "blocked" in str(exc).lower() or "chat not found" in str(exc).lower():
                    state["subscribers"].remove(cid)
    save_state(state)


async def post_init(app: Application) -> None:
    await app.bot.set_my_commands([
        BotCommand("bugun", "📅 Bugungi darslar"),
        BotCommand("ertaga", "🌅 Ertangi darslar"),
        BotCommand("hafta", "🗓 Bu haftaning darslari"),
        BotCommand("keyingi", "⏭ Keyingi dars"),
        BotCommand("toxtatish", "🔕 Eslatmalarni o'chirish"),
        BotCommand("start", "🔔 Botni ishga tushirish / eslatmalarni yoqish"),
    ])


def main() -> None:
    logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("BOT_TOKEN topilmadi. .env faylini yarating (.env.example ga qarang).")

    app = Application.builder().token(token).post_init(post_init).build()
    app.bot_data["state"] = load_state()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("toxtatish", cmd_stop))
    app.add_handler(CommandHandler("bugun", cmd_today))
    app.add_handler(CommandHandler("ertaga", cmd_tomorrow))
    app.add_handler(CommandHandler("hafta", cmd_week))
    app.add_handler(CommandHandler("keyingi", cmd_next))
    for label, fn in [(BTN_TODAY, cmd_today), (BTN_TOMORROW, cmd_tomorrow),
                      (BTN_WEEK, cmd_week), (BTN_NEXT, cmd_next)]:
        app.add_handler(MessageHandler(filters.Text([label]), fn))

    app.job_queue.run_repeating(tick, interval=TICK_SECONDS, first=5)
    log.info("Bot ishga tushdi: guruh %s, %d ta dars", GROUP, len(LESSONS))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
