import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message

BOT_TOKEN = ""
ALPHA_ID = 7399101034

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ---------------- DB ----------------
conn = sqlite3.connect("support.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS admins (
user_id INTEGER PRIMARY KEY,
role TEXT
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS tickets (
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
admin_id INTEGER
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS messages (
id INTEGER PRIMARY KEY AUTOINCREMENT,
ticket_id INTEGER,
admin_msg_id INTEGER,
user_id INTEGER
)""")

conn.commit()


# ---------------- HELPERS ----------------
def get_admins():
    cur.execute("SELECT user_id, role FROM admins")
    return cur.fetchall()

def support_admins():
    return [a[0] for a in get_admins() if a[1] != "alpha"]


def create_ticket(user_id):
    admins = support_admins()
    if not admins:
        return None, None

    cur.execute("SELECT COUNT(*) FROM tickets")
    count = cur.fetchone()[0]

    admin_id = admins[count % len(admins)]

    cur.execute("INSERT INTO tickets (user_id, admin_id) VALUES (?, ?)", (user_id, admin_id))
    conn.commit()

    return cur.lastrowid, admin_id


def get_user_by_admin_msg(msg_id):
    cur.execute("SELECT user_id FROM messages WHERE admin_msg_id=?", (msg_id,))
    r = cur.fetchone()
    return r[0] if r else None


# ---------------- USER → ADMIN ----------------
@dp.message()
async def user_handler(msg: Message):
    if msg.chat.id in [a[0] for a in get_admins()] or msg.chat.id == ALPHA_ID:
        return

    ticket_id, admin_id = create_ticket(msg.from_user.id)

    if not admin_id:
        return await msg.answer("❌ Admin yo‘q")

    admin_msg = await msg.forward(admin_id)

    # ALPHA monitoring (hamma ko‘radi)
    await msg.forward(ALPHA_ID)

    cur.execute(
        "INSERT INTO messages (ticket_id, admin_msg_id, user_id) VALUES (?, ?, ?)",
        (ticket_id, admin_msg.message_id, msg.from_user.id)
    )
    conn.commit()


# ---------------- ADMIN → USER ----------------
@dp.message(F.chat.id.in_([a[0] for a in get_admins()]))
async def admin_handler(msg: Message):
    if not msg.reply_to_message:
        return

    user_id = get_user_by_admin_msg(msg.reply_to_message.message_id)
    if not user_id:
        return

    # send clean response
    if msg.text:
        await bot.send_message(user_id, msg.text)
    elif msg.photo:
        await bot.send_photo(user_id, msg.photo[-1].file_id)
    elif msg.video:
        await bot.send_video(user_id, msg.video.file_id)
    elif msg.document:
        await bot.send_document(user_id, msg.document.file_id)
    elif msg.sticker:
        await bot.send_sticker(user_id, msg.sticker.file_id)
    elif msg.voice:
        await bot.send_voice(user_id, msg.voice.file_id)

    # ALPHA LOG
    await bot.send_message(
        ALPHA_ID,
        f"📌 Admin {msg.from_user.id} replied to user {user_id}"
    )


# ---------------- ALPHA PANEL ----------------
@dp.message(F.text.startswith("/addadmin"))
async def add_admin(msg: Message):
    if msg.from_user.id != ALPHA_ID:
        return

    _, uid, role = msg.text.split()
    cur.execute("INSERT OR REPLACE INTO admins VALUES (?, ?)", (int(uid), role))
    conn.commit()

    await msg.answer("✅ Admin qo‘shildi")


@dp.message(F.text == "/admins")
async def list_admins(msg: Message):
    if msg.from_user.id != ALPHA_ID:
        return

    cur.execute("SELECT * FROM admins")
    data = cur.fetchall()

    text = "👥 Adminlar:\n"
    for uid, role in data:
        text += f"{uid} — {role}\n"

    await msg.answer(text)


# ---------------- RUN ----------------
async def main():
    await dp.start_polling(bot)

asyncio.run(main())
