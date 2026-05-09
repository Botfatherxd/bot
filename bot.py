import asyncio
import time
from collections import defaultdict, deque

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

TOKEN = "8621141624:AAFZ3yh8uKqmfwi3QHMogJRDUC3_MW_hJpw"
BOT_USERNAME = "Zubikantiraidbot"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# =========================
# MEMORY STORAGE
# =========================

join_times = defaultdict(deque)  # chat_id -> join timestamps
spam_tracker = defaultdict(lambda: deque(maxlen=10))  # user_id -> message timestamps
last_messages = defaultdict(lambda: deque(maxlen=5))  # user_id -> last texts

raid_mode = defaultdict(bool)

# =========================
# UTIL
# =========================

def is_kxd_name(name: str) -> bool:
    return "kxd" in name.lower()

async def freeze_chat(chat_id: int):
    await bot.set_chat_permissions(
        chat_id,
        ChatPermissions(
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
            can_invite_users=False,
        )
    )

async def unfreeze_chat(chat_id: int):
    await bot.set_chat_permissions(
        chat_id,
        ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_invite_users=True,
        )
    )

# =========================
# START MESSAGE
# =========================

@dp.message(Command("start"))
async def start(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="➕ Добавить бота в чат",
            url=f"https://t.me/{BOT_USERNAME}?startgroup=true"
        )]
    ])

    await message.answer(
        "🤖 Anti-Raid Bot активен\n\nДобавь меня в чат для защиты от рейдов и спама.",
        reply_markup=kb
    )

# =========================
# ADMIN UNLOCK
# =========================

@dp.message(Command("unlock"))
async def unlock(message: Message):
    member = await bot.get_chat_member(message.chat.id, message.from_user.id)

    if member.status not in ["administrator", "creator"]:
        return await message.answer("❌ Только админы могут использовать эту команду.")

    raid_mode[message.chat.id] = False
    await unfreeze_chat(message.chat.id)

    await message.answer("🔓 Чат разблокирован. Режим рейда отключён.")

# =========================
# NEW MEMBERS (ANTI RAID)
# =========================

@dp.message(F.new_chat_members)
async def new_members(message: Message):
    chat_id = message.chat.id
    now = time.time()

    for user in message.new_chat_members:
        # KXD CHECK NAME
        if is_kxd_name(user.full_name):
            await bot.ban_chat_member(chat_id, user.id)
            await message.answer(f"⛔ {user.full_name} забанен (запрещённое имя).")
            return

        # RAID TRACKING
        join_times[chat_id].append(now)

    # remove old joins (10 sec window)
    while join_times[chat_id] and now - join_times[chat_id][0] > 10:
        join_times[chat_id].popleft()

    if len(join_times[chat_id]) >= 5:
        raid_mode[chat_id] = True

        await freeze_chat(chat_id)
        await message.answer("🚨 РЕЙД ОБНАРУЖЕН\n🔒 Чат заморожен")

# =========================
# ANTI SPAM + RAID LOCK
# =========================

@dp.message()
async def anti_spam(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    now = time.time()

    # ignore bots
    if message.from_user.is_bot:
        return

    # RAID MODE: block everyone except admins
    if raid_mode[chat_id]:
        member = await bot.get_chat_member(chat_id, user_id)
        if member.status not in ["administrator", "creator"]:
            return await message.delete()

    # SPAM TRACKING
    spam_tracker[user_id].append(now)
    last_messages[user_id].append(message.text or "")

    # too many messages (5 in 4 sec)
    if len(spam_tracker[user_id]) >= 5:
        if now - spam_tracker[user_id][0] < 4:
            await bot.ban_chat_member(chat_id, user_id)
            await message.answer("⛔ Спам detected → пользователь забанен")
            return

    # repeated messages flood
    if len(set(last_messages[user_id])) == 1 and len(last_messages[user_id]) == 5:
        await bot.ban_chat_member(chat_id, user_id)
        await message.answer("⛔ Флуд → бан")
        return

    # sticker/gif spam
    if message.sticker or message.animation:
        if len(spam_tracker[user_id]) >= 3:
            await bot.ban_chat_member(chat_id, user_id)
            await message.answer("⛔ Стикер/гиф спам → бан")

# =========================
# RUN
# =========================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
